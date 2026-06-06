# battle/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class BattleConsumer(AsyncWebsocketConsumer):
    """
    Handles the WebSocket connection for a battle room.

    Lifecycle:
        connect()    → player opens the battle page
        receive()    → player sends a message (code update, submit, etc.)
        disconnect() → player closes the tab or loses connection
    """

    # ─────────────────────────────────────────────
    # CONNECT
    # ─────────────────────────────────────────────

    async def connect(self):
        self.room_id    = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'battle_{self.room_id}'
        self.user       = self.scope['user']

        # reject unauthenticated connections
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # join the Redis channel group for this room
        await self.channel_layer.group_add(
            self.room_group,
            self.channel_name
        )

        # accept the WebSocket handshake
        await self.accept()

        # try to get battle — if it doesn't exist yet, handle gracefully
        battle = await self.get_battle()

        if battle is None:
            await self.send_json({
                'type':    'error',
                'message': f'Battle room {self.room_id} not found.'
            })
            await self.close()
            return

        # if this is player_b joining (room was waiting), start the battle
        if (battle.status == 'waiting'
                and battle.player_a
                and battle.player_a != self.user
                and not battle.player_b):
            battle = await self.set_player_b_and_start(battle)

        # send current battle state to this player
        await self.send_json({
            'type':       'battle_state',
            'room_id':    self.room_id,
            'status':     battle.status,
            'problem_id': battle.problem_id,
            'problem_title': await self.get_problem_title(battle),
            'player_a':   battle.player_a.username if battle.player_a else None,
            'player_b':   battle.player_b.username if battle.player_b else None,
            'time_limit': battle.time_limit_minutes * 60,
        })

        # notify everyone in the room that this player connected
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':   'player_event',
                'event':  'connected',
                'player': self.user.username,
            }
        )

    # ─────────────────────────────────────────────
    # RECEIVE — routes incoming messages by type
    # ─────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({'type': 'error', 'message': 'Invalid JSON'})
            return

        msg_type = data.get('type')

        if msg_type == 'code_update':
            await self.handle_code_update(data)

        elif msg_type == 'submit_code':
            await self.handle_submit(data)

        elif msg_type == 'chat':
            await self.handle_chat(data)

        elif msg_type == 'ping':
            # heartbeat — keep connection alive
            await self.send_json({'type': 'pong'})

        else:
            await self.send_json({
                'type':    'error',
                'message': f'Unknown message type: {msg_type}'
            })

    # ─────────────────────────────────────────────
    # DISCONNECT
    # ─────────────────────────────────────────────

    async def disconnect(self, close_code):
        # leave the Redis group
        await self.channel_layer.group_discard(
            self.room_group,
            self.channel_name
        )

        # notify others this player left
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.channel_layer.group_send(
                self.room_group,
                {
                    'type':       'player_event',
                    'event':      'disconnected',
                    'player':     self.user.username,
                    'close_code': close_code,
                }
            )

    # ─────────────────────────────────────────────
    # MESSAGE HANDLERS
    # called when group_send delivers a message here
    # ─────────────────────────────────────────────

    async def player_event(self, event):
        """Deliver player join/leave events to this browser."""
        await self.send_json(event)

    async def progress_update(self, event):
        """Deliver opponent's progress bar update to this browser."""
        # don't echo back to the player who sent it
        if event.get('player') != self.user.username:
            await self.send_json(event)

    async def verdict_event(self, event):
        """Deliver submission verdict to both players."""
        await self.send_json(event)

    async def chat_message(self, event):
        """Deliver chat message to this browser."""
        await self.send_json(event)

    async def battle_over(self, event):
        """Deliver battle over event to this browser."""
        await self.send_json(event)

    # ─────────────────────────────────────────────
    # HANDLE SPECIFIC MESSAGE TYPES
    # ─────────────────────────────────────────────

    async def handle_code_update(self, data):
        """
        Player typed more code — broadcast their line count
        to everyone else in the room as a progress update.
        """
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':   'progress_update',
                'player': self.user.username,
                'lines':  data.get('lines', 0),
                'lang':   data.get('lang', 'python'),
            }
        )

    async def handle_submit(self, data):
        """
        Player submitted code — save the submission,
        call the judge (Sprint 3), broadcast verdict.
        """
        code     = data.get('code', '').strip()
        language = data.get('language', 'python')

        if not code:
            await self.send_json({
                'type':    'error',
                'message': 'Cannot submit empty code.'
            })
            return

        # get the battle
        battle = await self.get_battle()
        if not battle or battle.status != 'active':
            await self.send_json({
                'type':    'error',
                'message': 'Battle is not active.'
            })
            return

        # save submission to DB
        submission = await self.save_submission(
            battle=battle,
            code=code,
            language=language,
        )

        # tell both players a submission is being judged
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':          'verdict_event',
                'player':        self.user.username,
                'verdict':       'JUDGING',
                'submission_id': submission.id,
            }
        )

        # ── judge call goes here in Sprint 3 ──
        # for now return a placeholder verdict
        verdict = await self.run_judge(code, language, battle)

        # update submission verdict in DB
        await self.update_submission_verdict(submission, verdict)

        # broadcast verdict to both players
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':          'verdict_event',
                'player':        self.user.username,
                'verdict':       verdict['verdict'],
                'time_ms':       verdict.get('time_ms'),
                'submission_id': submission.id,
            }
        )

        # if AC — end the battle
        if verdict['verdict'] == 'AC':
            await self.end_battle(battle, winner=self.user)

    async def handle_chat(self, data):
        """Broadcast a chat message to the room."""
        message = data.get('message', '').strip()[:500]  # cap at 500 chars
        if not message:
            return
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':    'chat_message',
                'player':  self.user.username,
                'message': message,
            }
        )

    # ─────────────────────────────────────────────
    # JUDGE (placeholder — real one in Sprint 3)
    # ─────────────────────────────────────────────

    async def run_judge(self, code, language, battle):
    """
    1. Fetches test cases from DB (on Django/Windows side)
    2. Sends them to the stateless FastAPI judge
    3. Returns verdict dict
    """
    import aiohttp

    # get test cases from DB — this runs on Django's side
    test_cases = await self.get_test_cases(battle)

    if not test_cases:
        return {
            'verdict': 'RE',
            'time_ms': 0,
            'passed':  0,
            'total':   0,
            'stderr':  'No test cases found for this problem.',
        }

    judge_url = 'http://127.0.0.1:8001/execute'

    payload = {
        'code':            code,
        'language':        language,
        'test_cases':      test_cases,   # pass them in the request
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
                    return {
                        'verdict': 'RE',
                        'time_ms': 0,
                        'passed':  0,
                        'total':   0,
                        'stderr':  f'Judge error {response.status}: {error}',
                    }

    except aiohttp.ClientConnectorError:
        print("[Consumer] Judge service not reachable at port 8001")
        return {
            'verdict': 'RE',
            'time_ms': 0,
            'passed':  0,
            'total':   0,
            'stderr':  'Judge service not running. Start uvicorn on port 8001.',
        }

    except Exception as e:
        return {
            'verdict': 'RE',
            'time_ms': 0,
            'passed':  0,
            'total':   0,
            'stderr':  f'Judge error: {str(e)}',
        }

    # ─────────────────────────────────────────────
    # BATTLE LIFECYCLE
    # ─────────────────────────────────────────────

    async def end_battle(self, battle, winner):
        """Mark battle finished and broadcast result."""
        await self.mark_battle_finished(battle, winner)

        await self.channel_layer.group_send(
            self.room_group,
            {
                'type':   'battle_over',
                'winner': winner.username,
                'loser':  (
                    battle.player_b.username
                    if winner == battle.player_a
                    else battle.player_a.username
                ) if battle.player_a and battle.player_b else None,
            }
        )

    # ─────────────────────────────────────────────
    # HELPER — send JSON cleanly
    # ─────────────────────────────────────────────

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))

    # ─────────────────────────────────────────────
    # DATABASE HELPERS — all sync wrapped with decorator
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
        if battle.problem:
            return battle.problem.title
        return None

    @database_sync_to_async
    def set_player_b_and_start(self, battle):
        battle.player_b  = self.user
        battle.status    = 'active'
        battle.started_at = timezone.now()
        battle.save()
        return battle

    @database_sync_to_async
    def save_submission(self, battle, code, language):
        from .models import Submission
        from problems.models import TestCase
        total = TestCase.objects.filter(
            problem=battle.problem, is_active=True
        ).count()
        return Submission.objects.create(
            battle=battle,
            player=self.user,
            code=code,
            language=language,
            total_test_cases=total,
        )

    @database_sync_to_async
    def update_submission_verdict(self, submission, verdict_data):
        submission.verdict          = verdict_data['verdict']
        submission.time_ms          = verdict_data.get('time_ms')
        submission.test_cases_passed = verdict_data.get('passed', 0)
        submission.save()

    @database_sync_to_async
    def mark_battle_finished(self, battle, winner):
        battle.winner      = winner
        battle.status      = 'finished'
        battle.finished_at = timezone.now()
        battle.save()

    @database_sync_to_async
    def get_test_cases(self, battle):
        """
        Reads test cases from DB and returns them as plain dicts.
        This runs in Django's thread pool (not the async event loop).
        """
        from problems.models import TestCase

        if not battle.problem:
            return []

        cases = TestCase.objects.filter(
            problem=battle.problem,
            is_active=True,
        ).order_by('order')

        return [
            {'input': tc.input_data, 'output': tc.expected_output}
            for tc in cases
        ]