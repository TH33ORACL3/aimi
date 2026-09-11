from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import model_discovery_notifier as notifier


class ModelDiscoveryNotifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / 'watcher-state.json'
        self.release_queue_path = Path(self.temp_dir.name) / 'release-queue.json'
        self.state_patch = patch.object(notifier, 'STATE', self.state_path)
        self.release_queue_patch = patch.object(
            notifier,
            'RELEASE_QUEUE',
            self.release_queue_path,
        )
        self.state_patch.start()
        self.release_queue_patch.start()

    def tearDown(self) -> None:
        self.release_queue_patch.stop()
        self.state_patch.stop()
        self.temp_dir.cleanup()

    def test_old_state_migrates_failure_snapshot(self) -> None:
        self.state_path.write_text(
            json.dumps(
                {
                    'version': 'model-catalogue-discovery-notifier/1.2',
                    'last_change_id': 10,
                    'last_provider_results': [
                        {'provider': 'gemini', 'status': 'failed', 'error': 'HTTP 403'}
                    ],
                }
            )
        )
        state = notifier.load_state()
        self.assertEqual(state['provider_failures'], {'gemini': 'HTTP 403'})
        self.assertIsNone(state['pending_notification'])

    def test_persistent_provider_failure_is_silent(self) -> None:
        previous = {'gemini': 'HTTP Error 403: Forbidden'}
        current = [
            {
                'provider': 'gemini',
                'status': 'failed',
                'error': 'HTTP Error 403: Forbidden',
            }
        ]
        self.assertEqual(notifier.failure_transitions(previous, current), ([], []))

    def test_provider_failure_change_and_recovery_are_alertable(self) -> None:
        previous = {'gemini': 'HTTP Error 403: Forbidden'}
        changed = [
            {'provider': 'gemini', 'status': 'failed', 'error': 'HTTP Error 429: Too Many Requests'}
        ]
        self.assertEqual(
            notifier.failure_transitions(previous, changed),
            ([('gemini', 'HTTP Error 429: Too Many Requests')], []),
        )

        recovered = [{'provider': 'gemini', 'status': 'unchanged'}]
        self.assertEqual(notifier.failure_transitions(previous, recovered), ([], ['gemini']))

    def test_route_addition_and_removal_are_queued_and_sent_once(self) -> None:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """SELECT 15 AS endpoint_change_id,
                      'openrouter' AS provider_id,
                      'example/new-model' AS model_identifier,
                      '2026-08-04T17:00:00+00:00' AS detected_at,
                      'Example: New Model' AS model_name,
                      NULL AS endpoint_first_seen_at,
                      1000 AS context_window_tokens,
                      200 AS max_output_tokens,
                      'paid' AS access_type,
                      'https://example.invalid/models' AS endpoint_url"""
        ).fetchone()
        body = notifier.format_notification(
            [row], [row], {('openrouter', 'example/new-model')}
        )
        self.assertIn('🆕 **ADDED:', body)
        self.assertIn('New AI model routes discovered (1)', body)
        self.assertIn('🗑️ **REMOVED:', body)
        self.assertIn('Model routes removed from their provider (1)', body)
        self.assertIn('🆕 ADDED', body)
        self.assertIn('🗑️ REMOVED', body)
        self.assertIn('ACTION NEEDED', body)
        self.assertLess(body.find('ACTION NEEDED'), body.find('**1. 🗑️ REMOVED'))
        self.assertIn('First seen:** 04 Aug 2026, 19:00:00 SAST', body)
        self.assertIn('Context window: 1,000 tokens', body)
        self.assertIn('Max input: Unknown', body)
        self.assertIn('Capabilities: Unknown', body)
        self.assertIn('AIMI endpoint monitor · local time', body)

        state = notifier.initial_state(10)
        with patch.object(notifier, 'deliver_notification', return_value={'message_id': '7'}) as sender:
            notifier.queue_and_deliver(state, body, 15, 'discovery')

        sender.assert_called_once_with(body)
        saved = json.loads(self.state_path.read_text())
        self.assertEqual(saved['last_change_id'], 15)
        self.assertIsNone(saved['pending_notification'])
        connection.close()

    def test_release_candidates_are_durable_and_deduplicated(self) -> None:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """SELECT 15 AS endpoint_change_id,
                      'openrouter' AS provider_id,
                      'OpenRouter' AS provider_name,
                      'example/new-model' AS model_identifier,
                      'Example: New Model' AS model_name,
                      '2026-08-12T16:00:00+00:00' AS detected_at,
                      'paid' AS access_type,
                      'https://example.invalid/models' AS endpoint_url,
                      'Endpoint observation only' AS description"""
        ).fetchone()

        self.assertEqual(notifier.enqueue_release_candidates([row]), 1)
        self.assertEqual(notifier.enqueue_release_candidates([row]), 0)

        queue = json.loads(self.release_queue_path.read_text())
        self.assertEqual(len(queue['pending']), 1)
        self.assertEqual(queue['pending'][0]['endpoint_change_id'], 15)
        self.assertEqual(queue['pending'][0]['model_identifier'], 'example/new-model')
        self.assertEqual(queue['pending'][0]['attempts'], 0)
        connection.close()

    def test_bulk_origin_discovery_is_not_queued_for_editorial_news(self) -> None:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        rows = [
            connection.execute(
                """SELECT ? AS endpoint_change_id,
                          77 AS monitoring_run_id,
                          12 AS monitoring_run_added_count,
                          'openai' AS provider_id,
                          ? AS model_identifier,
                          '2026-08-26T12:15:46+00:00' AS detected_at""",
                (100 + position, f'legacy/model-{position}'),
            ).fetchone()
            for position in range(12)
        ]

        eligible, suppressed = notifier.filter_news_candidates(rows)

        self.assertEqual(eligible, [])
        self.assertEqual(len(suppressed), 12)
        self.assertTrue(
            all(
                item['news_eligibility_reason'] == 'bulk_endpoint_sync'
                for item in suppressed
            )
        )
        self.assertEqual(notifier.enqueue_release_candidates(rows), 0)
        self.assertFalse(self.release_queue_path.exists())
        body = notifier.format_notification(rows, [], set(), suppressed=suppressed)
        self.assertIn('🔄 **RESYNC:', body)
        self.assertIn('Bulk model catalogue sync (12 routes; no editorial candidates)', body)
        self.assertNotIn('legacy/model-0', body)
        self.assertIn('withheld from the website/X news queue', body)
        connection.close()

    def test_same_day_official_release_overrides_bulk_suppression(self) -> None:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """SELECT 200 AS endpoint_change_id,
                      88 AS monitoring_run_id,
                      12 AS monitoring_run_added_count,
                      'openai' AS provider_id,
                      'new/model' AS model_identifier,
                      '2026-08-26T12:15:46+00:00' AS detected_at,
                      1 AS same_day_official_release,
                      'OpenAI: New Model' AS model_name,
                      'https://example.invalid/models' AS endpoint_url"""
        ).fetchone()

        eligible, suppressed = notifier.filter_news_candidates([row])

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]['news_eligibility_reason'], 'same_day_official_release')
        self.assertEqual(suppressed, [])
        self.assertEqual(notifier.enqueue_release_candidates([row]), 1)
        queue = json.loads(self.release_queue_path.read_text())
        self.assertEqual(
            queue['pending'][0]['news_eligibility_reason'],
            'same_day_official_release',
        )
        connection.close()

    def test_single_origin_endpoint_observation_is_not_editorial_news(self) -> None:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """SELECT 210 AS endpoint_change_id,
                      89 AS monitoring_run_id,
                      1 AS monitoring_run_added_count,
                      'openai' AS provider_id,
                      'old/model' AS model_identifier,
                      '2026-08-26T12:15:46+00:00' AS detected_at"""
        ).fetchone()

        eligible, suppressed = notifier.filter_news_candidates([row])

        self.assertEqual(eligible, [])
        self.assertEqual(
            suppressed[0]['news_eligibility_reason'],
            'endpoint_observation_without_release',
        )
        body = notifier.format_notification([row], [], set(), suppressed=suppressed)
        self.assertIn('📡 **ROUTE OBSERVATION:', body)
        self.assertNotIn('🆕 **ADDED:', body)
        self.assertNotIn('Bulk model catalogue sync', body)
        connection.close()

    def test_failed_delivery_keeps_pending_and_does_not_advance_watermark(self) -> None:
        state = notifier.initial_state(10)
        state['pending_notification'] = notifier.pending_record('route alert', 15, 'discovery')
        notifier.save_state(state)

        with patch.object(notifier, 'deliver_notification', side_effect=notifier.DeliveryError('offline')):
            with self.assertRaises(notifier.DeliveryError):
                notifier.deliver_pending(state)

        saved_after_failure = json.loads(self.state_path.read_text())
        self.assertEqual(saved_after_failure['last_change_id'], 10)
        self.assertEqual(saved_after_failure['pending_notification']['attempts'], 1)
        self.assertEqual(saved_after_failure['pending_notification']['body'], 'route alert')

    def test_successful_retry_advances_watermark_once(self) -> None:
        state = notifier.initial_state(10)
        state['pending_notification'] = notifier.pending_record('route alert', 15, 'discovery')
        notifier.save_state(state)

        with patch.object(notifier, 'deliver_notification', return_value={'message_id': '42'}) as sender:
            notifier.deliver_pending(state)
            notifier.deliver_pending(state)

        sender.assert_called_once_with('route alert')
        saved = json.loads(self.state_path.read_text())
        self.assertEqual(saved['last_change_id'], 15)
        self.assertIsNone(saved['pending_notification'])
        self.assertEqual(saved['last_delivery']['message_id'], '42')

    def test_pending_delivery_failure_stops_before_another_poll(self) -> None:
        state = notifier.initial_state(10)
        state['pending_notification'] = notifier.pending_record('route alert', 15, 'discovery')
        notifier.save_state(state)

        with patch.object(notifier, 'deliver_notification', side_effect=notifier.DeliveryError('offline')):
            with patch.object(notifier, 'run_aimi_script') as monitor:
                self.assertEqual(notifier.run_locked(), 1)
                monitor.assert_not_called()

    def test_hard_failure_does_not_advance_discovery_watermark(self) -> None:
        state = notifier.initial_state(10)
        with patch.object(notifier, 'deliver_notification', return_value={'message_id': '8'}):
            self.assertEqual(notifier.handle_hard_failure(state, 99, RuntimeError('ingest failed')), 0)

        saved = json.loads(self.state_path.read_text())
        self.assertEqual(saved['last_change_id'], 10)
        self.assertIsNone(saved['pending_notification'])
        self.assertIn('ingest failed', saved['last_hard_error'])

    def test_hermes_ok_false_is_a_delivery_failure(self) -> None:
        def fake_runner(command, **kwargs):
            return CompletedProcess(
                command,
                0,
                stdout=json.dumps({'payload': {'ok': False, 'error': 'adapter down'}}),
                stderr='',
            )

        with patch.object(notifier, 'hermes_binary', return_value='/fake/hermes'):
            with self.assertRaises(notifier.DeliveryError):
                notifier.send_via_hermes('hello', runner=fake_runner, sleep_fn=lambda _: None)

    def test_hermes_send_retries_without_network_access_in_test(self) -> None:
        calls: list[str] = []

        def fake_runner(command, **kwargs):
            calls.append(Path(kwargs['args'] if 'args' in kwargs else command[command.index('--file') + 1]).read_text())
            if len(calls) == 1:
                return CompletedProcess(command, 1, stdout='', stderr='temporary failure')
            return CompletedProcess(
                command,
                0,
                stdout=json.dumps({'payload': {'ok': True, 'messageId': '99'}}),
                stderr='',
            )

        with patch.object(notifier, 'hermes_binary', return_value='/fake/hermes'):
            result = notifier.send_via_hermes('hello', runner=fake_runner, sleep_fn=lambda _: None)

        self.assertEqual(calls, ['hello', 'hello'])
        self.assertEqual(result['message_id'], '99')

    def test_local_time_formatter_converts_utc_to_sast(self) -> None:
        self.assertEqual(
            notifier.format_local_time('2026-08-05T08:28:48+00:00'),
            '05 Aug 2026, 10:28:48 SAST',
        )

    def test_message_is_bounded_for_telegram(self) -> None:
        bounded = notifier.bound_message('x' * (notifier.MAX_MESSAGE_CHARS + 500))
        self.assertLessEqual(len(bounded), notifier.MAX_MESSAGE_CHARS + 80)
        self.assertIn('message truncated', bounded)

    def test_split_message_preserves_content_and_part_limit(self) -> None:
        text = '\n\n'.join(f'Route {position}: ' + ('x' * 45) for position in range(12))
        parts = notifier.split_message(text, limit=160)

        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= 160 for part in parts))
        for position in range(12):
            self.assertIn(f'Route {position}:', '\n'.join(parts))
        self.assertIn('part 1/', parts[0])
        self.assertNotIn(r'\n', '\n'.join(parts))

    def test_multipart_pending_resumes_at_failed_part(self) -> None:
        state = notifier.initial_state(10)
        state['pending_notification'] = notifier.pending_record(
            ['part one', 'part two', 'part three'], 15, 'discovery'
        )
        notifier.save_state(state)
        calls: list[str] = []

        def sender(body: str) -> dict:
            calls.append(body)
            if len(calls) == 2:
                raise notifier.DeliveryError('offline')
            return {'message_id': str(len(calls))}

        with patch.object(notifier, 'deliver_notification', side_effect=sender):
            with self.assertRaises(notifier.DeliveryError):
                notifier.deliver_pending(state)

        saved_after_failure = json.loads(self.state_path.read_text())
        self.assertEqual(saved_after_failure['pending_notification']['part_index'], 1)
        self.assertEqual(saved_after_failure['pending_notification']['body'], 'part two')
        self.assertEqual(saved_after_failure['last_change_id'], 10)

        with patch.object(notifier, 'deliver_notification', return_value={'message_id': 'retry'}) as retry:
            notifier.deliver_pending(state)

        retry.assert_any_call('part two')
        retry.assert_any_call('part three')
        saved = json.loads(self.state_path.read_text())
        self.assertEqual(saved['last_change_id'], 15)
        self.assertIsNone(saved['pending_notification'])
        self.assertEqual(saved['last_delivery']['part_count'], 3)


if __name__ == '__main__':
    unittest.main()
