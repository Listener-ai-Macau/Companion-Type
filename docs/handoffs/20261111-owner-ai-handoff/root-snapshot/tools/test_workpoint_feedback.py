"""Regression coverage for stale/repeated customer handoff decisions; no product I/O."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest


class FeedbackWorkpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        spec = importlib.util.spec_from_file_location(
            'backlog_workpoint_fixture', Path(__file__).with_name('render_product_backlog.py'))
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.ROOT = self.root
        self.module.SOURCE = self.root / 'docs/product_backlog.json'
        self.loop = {'feedbackIndex': [], 'currentWorkpoint': {'next': 'Current action'},
                     'nextEngineeringWorkpoint': 'Retired action'}
        self.data = {'screen_interaction_core': {'customer_engineering_loop_20261020': self.loop}}

    def artifact(self, relative, seconds):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Explicit fixture, not customer feedback', encoding='utf-8')
        os.utime(path, (seconds, seconds))
        return path

    def result(self, focus='screen'):
        return self.module.read_workpoint(self.data, b'{}', focus)

    def test_processed_absolute_and_historical_evidence_paths_are_not_new(self):
        first = self.artifact('.cache/pet-goal-20261013/customer-use-one/customer-experience.txt', 1)
        second = self.artifact('.cache/pet-goal-20261013/customer-use-two/customer-experience.txt', 2)
        self.loop['feedbackIndex'] = [
            {'raw': str(first.resolve()), 'processed': True},
            {'evidence': second.relative_to(self.root).as_posix()}]
        result = self.result()
        self.assertEqual(result['unprocessedCustomerArtifactCount'], 0)
        self.assertEqual(result['requiredAction']['kind'], 'CONTINUE_RECORDED_WORKPOINT')
        self.assertEqual(result['next'], 'Current action')

    def test_raw_feedback_alias_keeps_older_history_out_of_next_action(self):
        self.artifact('.cache/pet-goal-20261013/customer-use-old/customer-experience.txt', 1)
        latest = self.artifact('.cache/pet-goal-20261013/batch/aftercare/customer/customer-experience.txt', 10)
        self.loop['latestCustomerReturn'] = {'rawFeedback': str(latest)}
        self.assertEqual(self.result()['unprocessedCustomerArtifactCount'], 0)

    def test_new_nested_live_customer_is_received_without_recursive_history_scan(self):
        latest = self.artifact('.cache/pet-goal-20261013/last/customer-experience.txt', 10)
        self.loop['latestCustomerReturn'] = {'raw': str(latest)}
        fresh = self.artifact('.cache/pet-goal-20261013/batch/presale/customer/customer-experience.txt', 20)
        entry = fresh.parents[1] / 'entry.json'
        entry.write_text(json.dumps({'customerPath': str(fresh.parent)}), encoding='utf-8')
        self.loop['handoffPosition'] = {'runningCustomer': {'entry': str(entry)}}
        result = self.result()
        self.assertEqual(result['unprocessedCustomerArtifactCount'], 1)
        self.assertEqual(result['requiredAction']['raw'], fresh.relative_to(self.root).as_posix())
        # A screen-only fixture must not become an embedded task by fallback.
        with self.assertRaisesRegex(ValueError,'current embedded plan'):
            self.result('recorder')

    def test_explicit_unprocessed_feedback_still_requires_receiving(self):
        fresh = self.artifact('.cache/pet-goal-20261013/customer-use-open/customer-experience.txt', 20)
        self.loop['feedbackIndex'] = [{'raw': str(fresh), 'processed': False}]
        self.assertEqual(self.result()['unprocessedCustomerArtifactCount'], 1)

    def test_declared_feature_return_name_retires_older_processed_history(self):
        self.artifact('.cache/pet-goal-20261013/customer-use-old/customer-experience.txt', 1)
        latest = self.artifact('.cache/pet-goal-20261013/batch/customer/personality-feature-return.txt', 10)
        self.loop['latestCustomerReturn'] = {'rawFeedback': str(latest)}
        self.assertEqual(self.result()['unprocessedCustomerArtifactCount'], 0)

    def test_explicit_pending_feature_survives_newer_other_return(self):
        latest = self.artifact('.cache/pet-goal-20261013/last/customer-experience.txt', 10)
        pending = self.artifact('.cache/pet-goal-20261013/batch/customer/personality-feature-return.txt', 5)
        self.loop['latestCustomerReturn'] = {'rawFeedback': str(latest)}
        self.loop['feedbackIndex'] = [{'raw': str(pending), 'processed': False}]
        result = self.result()
        self.assertEqual(result['unprocessedCustomerArtifactCount'], 1)
        self.assertEqual(result['requiredAction']['raw'], pending.relative_to(self.root).as_posix())

    def test_handled_current_round_replaces_stale_customer_alias(self):
        old=self.artifact('.cache/pet-goal-20261013/old/customer-experience.txt',1)
        new=self.artifact('.cache/pet-goal-20261013/new/customer-experience.txt',2)
        self.loop['latestCustomerReturn']={'stage':'Old round','raw':str(old)}
        self.loop['currentRound']={'stage':'Current round','raw':[str(new)],'state':'COMPLETE'}
        self.loop['feedbackIndex']=[{'raw':str(new),'processed':True}]
        result=self.result()
        self.assertEqual(result['lastCustomer']['stage'],'Current round')
        self.assertEqual(result['lastCustomer']['raw'],[str(new.resolve())])
        self.assertEqual(result['unprocessedCustomerArtifactCount'],0)

    def test_current_round_does_not_mark_unread_feedback_handled(self):
        new=self.artifact('.cache/pet-goal-20261013/new/customer-experience.txt',2)
        self.loop['currentRound']={'stage':'Current round','raw':[str(new)]}
        result=self.result()
        self.assertEqual(result['unprocessedCustomerArtifactCount'],1)
        self.assertEqual(result['requiredAction']['kind'],'RECEIVE_CUSTOMER_FEEDBACK')

    def test_explicit_open_latest_alias_is_not_silently_handled(self):
        new=self.artifact('.cache/pet-goal-20261013/new/customer-experience.txt',2)
        self.loop['latestCustomerReturn']={'raw':str(new)}
        self.loop['feedbackIndex']=[{'raw':str(new),'processed':False}]
        self.assertEqual(self.result()['unprocessedCustomerArtifactCount'],1)

    def test_read_receipt_is_not_reissued_but_an_amendment_is(self):
        old=self.artifact('docs/releases/20261020-rate-old.json',1)
        new=self.artifact('docs/releases/20261027-rate-new.json',2)
        self.loop['latestSharedFirmwareDelivery']={'latestRecorderReceipt':old.relative_to(self.root).as_posix()}
        self.loop['sharedReceiptReads']={new.relative_to(self.root).as_posix():
            {'sha256':hashlib.sha256(new.read_bytes()).hexdigest()}}
        self.assertEqual(self.result()['requiredAction']['kind'],'CONTINUE_RECORDED_WORKPOINT')
        new.write_text('Changed evidence, needs reading again',encoding='utf-8')
        # Even a receipt restored with its old timestamp must not hide edits.
        os.utime(new,(2,2))
        result=self.result()
        self.assertEqual(result['unprocessedSharedReceiptCount'],1)
        self.assertEqual(result['requiredAction']['kind'],'READ_NEW_SHARED_DELIVERY_RECEIPTS')
        self.assertEqual(result['requiredAction']['raw'],new.relative_to(self.root).as_posix())
        # Missing canonical embedded work must not silently resume an old job.
        with self.assertRaisesRegex(ValueError,'current embedded plan'):
            self.result('recorder')

    def test_new_receipt_still_interrupts_an_acknowledged_batch(self):
        old=self.artifact('docs/releases/20261020-rate-old.json',1)
        read=self.artifact('docs/releases/20261021-rate-read.json',2)
        fresh=self.artifact('docs/releases/20261027-rate-fresh.json',3)
        self.loop['latestSharedFirmwareDelivery']={'latestRecorderReceipt':old.relative_to(self.root).as_posix()}
        self.loop['sharedReceiptReads']={read.relative_to(self.root).as_posix():
            {'sha256':hashlib.sha256(read.read_bytes()).hexdigest()}}
        result=self.result()
        self.assertEqual(result['unprocessedSharedReceiptCount'],1)
        self.assertEqual(result['requiredAction']['raw'],fresh.relative_to(self.root).as_posix())


if __name__ == '__main__':
    unittest.main()
