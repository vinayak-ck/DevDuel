# battle/consumers.py
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class BattleConsumer(AsyncWebsocketConsumer):

    # ─────────────────────────────────────────────
    # CONNECT
    # ─────────────────────────────────────────────

    async def connect(self):
        self.room_id    = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'battle_{self.room_id}'
        self.user       = self.scope['user']

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # accept FIRST — so browser knows connection succeeded
        await self.accept()

        # join Redis group — wrap in try so a Redis hiccup doesn't kill the WS
        try:
            await self.channel_layer.group_add(self.room_group, self.channel_name)
        except Exception as e:
            print(f"[WS] group_add failed for {self.room_id}: {e}")

        battle = await self.get_battle()

        if battle is None:
            await self.send_json({'type': 'error', 'message': f'Room {self.room_id} not found.'})
            await self.close()
            return

        # player_b joining a waiting room
        if (battle.status == 'waiting'
                and battle.player_a
                and battle.player_a != self.user
                and not battle.player_b):
            battle = await self.set_player_b_and_start(battle)

        # always send battle_state directly (not via Redis)
        # this guarantees the player knows the current state
        await self.send_json({
            'type':          'battle_state',
            'room_id':       self.room_id,
            'status':        battle.status,
            'problem_id':    battle.problem_id,
            'problem_title': await self.get_problem_title(battle),
            'player_a':      battle.player_a.username if battle.player_a else None,
            'player_b':      battle.player_b.username if battle.player_b else None,
            'time_limit':    battle.time_limit_minutes * 60,
        })

        # notify room this player joined
        await self.safe_group_send(self.room_group, {
            'type':   'player_event',
            'event':  'connected',
            'player': self.user.username,
        })

    # ─────────────────────────────────────────────
    # RECEIVE
    # ─────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({'type': 'error', 'message': 'Invalid JSON'})
            return

        msg_type = data.get('type')

        if   msg_type == 'code_update': await self.handle_code_update(data)
        elif msg_type == 'submit_code': await self.handle_submit(data)
        elif msg_type == 'chat':        await self.handle_chat(data)
        elif msg_type == 'ping':        await self.send_json({'type': 'pong'})
        else:
            await self.send_json({'type': 'error', 'message': f'Unknown type: {msg_type}'})

    # ─────────────────────────────────────────────
    # DISCONNECT
    # ─────────────────────────────────────────────

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
        except Exception as e:
            print(f"[WS] group_discard failed: {e}")

        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.safe_group_send(self.room_group, {
                'type':       'player_event',
                'event':      'disconnected',
                'player':     self.user.username,
                'close_code': close_code,
            })

    # ─────────────────────────────────────────────
    # GROUP MESSAGE HANDLERS
    # ─────────────────────────────────────────────

    async def player_event(self, event):
        await self.send_json(event)

    async def progress_update(self, event):
        if event.get('player') != self.user.username:
            await self.send_json(event)

    async def verdict_event(self, event):
        await self.send_json(event)

    async def chat_message(self, event):
        await self.send_json(event)

    async def battle_over(self, event):
        await self.send_json(event)

    # ─────────────────────────────────────────────
    # MESSAGE HANDLERS
    # ─────────────────────────────────────────────

    async def handle_code_update(self, data):
        await self.safe_group_send(self.room_group, {
            'type':   'progress_update',
            'player': self.user.username,
            'lines':  data.get('lines', 0),
            'lang':   data.get('lang', 'python'),
        })

    async def handle_submit(self, data):
        code     = data.get('code', '').strip()
        language = data.get('language', 'python')

        if not code:
            await self.send_json({'type': 'error', 'message': 'Cannot submit empty code.'})
            return

        battle = await self.get_battle()
        if not battle or battle.status != 'active':
            await self.send_json({'type': 'error', 'message': 'Battle is not active.'})
            return

        submission = await self.save_submission(battle, code, language)

        # tell both players judging started
        judging_msg = {
            'type':          'verdict_event',
            'player':        self.user.username,
            'verdict':       'JUDGING',
            'submission_id': submission.id,
        }
        await self.safe_group_send(self.room_group, judging_msg)
        # also send directly to self — guaranteed delivery
        await self.send_json(judging_msg)

        # call the judge
        verdict = await self.run_judge(code, language, battle)

        # save to DB
        await self.update_submission_verdict(submission, verdict)

        # build verdict message
        verdict_msg = {
            'type':          'verdict_event',
            'player':        self.user.username,
            'verdict':       verdict['verdict'],
            'time_ms':       verdict.get('time_ms'),
            'tests_passed':  verdict.get('passed', 0),
            'tests_total':   verdict.get('total', 0),
            'stderr':        verdict.get('stderr', ''),
            'submission_id': submission.id,
        }

        # send to group with retry
        await self.safe_group_send(self.room_group, verdict_msg)
        # ALSO send directly to self — so submitter ALWAYS gets their verdict
        # even if Redis group_send fails
        await self.send_json(verdict_msg)

        if verdict['verdict'] == 'AC':
            await self.end_battle(battle, winner=self.user)

    async def handle_chat(self, data):
        message = data.get('message', '').strip()[:500]
        if not message:
            return
        await self.safe_group_send(self.room_group, {
            'type':    'chat_message',
            'player':  self.user.username,
            'message': message,
        })

    # ─────────────────────────────────────────────
    # SAFE GROUP SEND — retries + direct fallback
    # ─────────────────────────────────────────────

    async def safe_group_send(self, group, message):
        """
        group_send with 3 retries on Redis timeout.
        If all retries fail, sends directly to self as fallback.
        This ensures the submitting player always gets their verdict
        even if Redis is having a bad moment.
        """
        for attempt in range(3):
            try:
                await self.channel_layer.group_send(group, message)
                return  # success
            except Exception as e:
                print(f"[WS] group_send attempt {attempt+1}/3 failed "
                      f"(type={message.get('type')}): {e}")
                if attempt < 2:
                    await asyncio.sleep(0.2 * (attempt + 1))

        # all retries failed — send directly to self
        print(f"[WS] All retries failed, sending directly to self "
              f"(type={message.get('type')})")
        try:
            await self.send_json(message)
        except Exception as e:
            print(f"[WS] Direct fallback also failed: {e}")

    # ─────────────────────────────────────────────
    # JUDGE
    # ─────────────────────────────────────────────

    async def run_judge(self, code, language, battle):
        import aiohttp
        from django.conf import settings

        test_cases = await self.get_test_cases(battle)
        if not test_cases:
            return {'verdict': 'RE', 'time_ms': 0, 'passed': 0,
                    'total': 0, 'stderr': 'No test cases found.'}

        judge_url = f"{settings.JUDGE_URL}/execute"
        print(f"[Judge] Calling: {judge_url}")

        payload = {
            'code':            code,
            'language':        language,
            'test_cases':      test_cases,
            'time_limit':      battle.problem.time_limit_seconds if battle.problem else 5.0,
            'memory_limit_mb': battle.problem.memory_limit_mb   if battle.problem else 256,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    judge_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'verdict':      data['verdict'],
                            'time_ms':      data['time_ms'],
                            'passed':       data['tests_passed'],
                            'total':        data['tests_total'],
                            'stderr':       data.get('stderr', ''),
                            'test_results': data.get('test_results', []),
                        }
                    else:
                        error = await response.text()
                        return {'verdict': 'RE', 'time_ms': 0, 'passed': 0,
                                'total': 0, 'stderr': f'Judge {response.status}: {error}'}

        except aiohttp.ClientConnectorError:
            print("[Judge] Cannot reach judge service")
            return {'verdict': 'RE', 'time_ms': 0, 'passed': 0, 'total': 0,
                    'stderr': 'Judge service unreachable. Check JUDGE_URL.'}
        except Exception as e:
            return {'verdict': 'RE', 'time_ms': 0, 'passed': 0,
                    'total': 0, 'stderr': f'Judge error: {str(e)}'}

    # ─────────────────────────────────────────────
    # BATTLE LIFECYCLE
    # ─────────────────────────────────────────────

    async def end_battle(self, battle, winner):
        from .services import process_battle_result
        await self.mark_battle_finished(battle, winner)

        try:
            rating_data = await process_battle_result(battle.id, winner.username)
        except Exception as e:
            print(f"[ELO] Failed to process result: {e}")
            rating_data = {}

        loser_username = None
        if battle.player_a and battle.player_b:
            loser_username = (
                battle.player_b.username if winner == battle.player_a
                else battle.player_a.username
            )

        battle_over_msg = {
            'type':           'battle_over',
            'winner':         winner.username,
            'loser':          loser_username,
            'rating_changes': rating_data,
        }
        await self.safe_group_send(self.room_group, battle_over_msg)
        await self.send_json(battle_over_msg)

    # ─────────────────────────────────────────────
    # UTILITY
    # ─────────────────────────────────────────────

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))

    # ─────────────────────────────────────────────
    # DATABASE HELPERS
    # ─────────────────────────────────────────────

    @database_sync_to_async
    def get_battle(self):
        from .models import Battle
        try:
            return Battle.objects.select_related(
                'player_a', 'player_b', 'problem', 'winner'
            ).get(room_id=self.room_id)
        except Battle.DoesNotExist:
            return None

    @database_sync_to_async
    def get_problem_title(self, battle):
        return battle.problem.title if battle.problem else None

    @database_sync_to_async
    def set_player_b_and_start(self, battle):
        battle.player_b   = self.user
        battle.status     = 'active'
        battle.started_at = timezone.now()
        battle.save()
        return battle

    @database_sync_to_async
    def save_submission(self, battle, code, language):
        from .models import Submission
        from problems.models import TestCase
        total = TestCase.objects.filter(problem=battle.problem, is_active=True).count()
        return Submission.objects.create(
            battle=battle, player=self.user,
            code=code, language=language, total_test_cases=total,
        )

    @database_sync_to_async
    def update_submission_verdict(self, submission, verdict_data):
        submission.verdict           = verdict_data['verdict']
        submission.time_ms           = verdict_data.get('time_ms')
        submission.test_cases_passed = verdict_data.get('passed', 0)
        submission.stderr            = verdict_data.get('stderr', '')
        submission.save()

    @database_sync_to_async
    def mark_battle_finished(self, battle, winner):
        battle.winner      = winner
        battle.status      = 'finished'
        battle.finished_at = timezone.now()
        battle.save()

    @database_sync_to_async
    def get_test_cases(self, battle):
        from problems.models import TestCase
        if not battle.problem_id:
            return []
        cases = TestCase.objects.filter(
            problem_id=battle.problem_id, is_active=True
        ).order_by('order')
        result = [{'input': tc.input_data, 'output': tc.expected_output} for tc in cases]
        print(f"[Judge] Found {len(result)} test cases for problem_id={battle.problem_id}")
        return result