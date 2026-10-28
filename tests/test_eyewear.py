import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from driver_monitor.eyewear import EyewearGate, EyeRouter
from driver_monitor.config import Config, ROOT, load_config
from driver_monitor.core import Monitor, Observation


class GateTests(unittest.TestCase):
    def test_only_fresh_repeated_confident_glasses_scores_enable_specialist(self):
        gate=EyewearGate()
        for i in range(16):
            route=gate.update(i/10,.999 if gate.needs_score(i/10) else None)
            self.assertEqual(route.branch,'glasses' if i==15 else 'original')
        self.assertTrue(route.changed)

    def test_one_score_never_confirms_and_ambiguous_score_returns_original_immediately(self):
        gate=EyewearGate()
        for i in range(21):route=gate.update(i/10,.999 if i==0 else None)
        self.assertEqual(route.branch,'original');self.assertIsNone(route.probability)
        for i in range(21,42):route=gate.update(i/10,.999 if gate.needs_score(i/10) else None)
        self.assertEqual(route.branch,'glasses')
        route=gate.update(4.2,.75)
        self.assertEqual(route.branch,'original');self.assertTrue(route.changed)

    def test_gap_track_change_bad_quality_and_reversed_timestamp_reset(self):
        for fault in ('gap','track','quality','reverse'):
            gate=EyewearGate()
            for i in range(21):gate.update(i/10,.999 if gate.needs_score(i/10) else None)
            self.assertEqual(gate.branch,'glasses')
            route=gate.update(2.6 if fault=='gap' else 1.9 if fault=='reverse' else 2.1,.999,
                              valid=fault!='quality',track_changed=fault=='track')
            self.assertEqual(route.branch,'original',fault);self.assertTrue(route.changed)

    def test_no_glasses_or_uncertain_scores_keep_original(self):
        gate=EyewearGate()
        for i in range(200):
            route=gate.update(i/10,[.001,.1,.5,.9,.98][(i//5)%5] if gate.needs_score(i/10) else None)
            self.assertEqual(route.branch,'original');self.assertFalse(route.changed)

    def test_invalid_probability_and_policy_are_rejected(self):
        for p in (float('nan'),-.1,1.1):
            with self.assertRaises(ValueError):EyewearGate().update(0,p)
        with self.assertRaises(ValueError):EyewearGate(poll_seconds=1,max_score_age_seconds=.8)


class RoutingTests(unittest.TestCase):
    def make_router(self):
        original=object();specialist=SimpleNamespace(close=lambda:None,predict=lambda _:None)
        selector=SimpleNamespace(manifest={'gate':{'enter_probability':.99,'confirm_seconds':1.5,'poll_seconds':.5,'max_score_age_seconds':.8}},
                                 predict=lambda _: .999,close=lambda:None)
        with patch('driver_monitor.eyewear.EyewearModel',return_value=selector),patch('driver_monitor.eyewear.Classifier',return_value=specialist) as factory:
            router=EyeRouter(original,Config(auto_glasses=True))
        self.assertEqual(factory.call_args.args[1],'eye')
        return router,original,specialist,selector

    def test_routes_only_eye_and_transition_interrupts_eyes_without_changing_yawn_events(self):
        router,original,specialist,_=self.make_router();observed=Monitor();control=Monitor();routes=[]
        for i in range(36):
            t=i/10;result=SimpleNamespace(quality='usable',eye_quality='usable',crops=(object(),object(),object()),metrics={},track_changed=False)
            model,route=router.select(result,t);routes.append(route.branch)
            self.assertIs(model,specialist if route.branch=='glasses' else original)
            closed={'Closed':.99,'Open':.01};mouth={'yawn':.99,'no_yawn':.01}
            a=observed.update(Observation(t,closed,closed,mouth,eye_quality=result.eye_quality))
            b=control.update(Observation(t,closed,closed,mouth))
            self.assertEqual((a.yawn_state,a.yawn_count,a.yawn_probability),(b.yawn_state,b.yawn_count,b.yawn_probability))
            if route.changed:
                self.assertEqual(a.state,'UNKNOWN');self.assertEqual(a.eye_closed_seconds,0)
        self.assertIn('glasses',routes)
        self.assertEqual(a.yawn_count,1)

    def test_selector_fault_falls_back_to_original_without_calling_specialist(self):
        router,original,_,selector=self.make_router()
        selector.predict=lambda _: (_ for _ in ()).throw(RuntimeError('selector unavailable'))
        result=SimpleNamespace(quality='usable',eye_quality='usable',crops=(object(),)*3,metrics={},track_changed=False)
        model,route=router.select(result,0.)
        self.assertIs(model,original);self.assertIn('selector unavailable',router.error)
        self.assertEqual(route.branch,'original')

    def test_original_configuration_fingerprints_remain_unchanged(self):
        expected={'configs/camera_pc.yaml':'8f1bd2490171f960bd35dac2af822d55e6a8a616a1ff4dacbde6cb603ff6c476',
                  'configs/driver_monitor.yaml':'1cb4a6cc635a99a9accdc20b168f42b178bcb88bd4922390ddde2a2dccb38b16'}
        for path,fingerprint in expected.items():
            self.assertEqual(load_config(ROOT/path).fingerprint(),fingerprint)

    @unittest.skipUnless((ROOT/'models/yawn_kaggle_near_medium/runtime.yaml').is_file(),
                         'Optional local near/medium profile is not installed')
    def test_local_near_medium_configuration_fingerprint_remains_unchanged(self):
        config=load_config(ROOT/'models/yawn_kaggle_near_medium/runtime.yaml')
        self.assertEqual(config.fingerprint(),'c6ede5290fea6ebc1365fed162d2f386e451e7984b0280a3907b672ef17e1086')


if __name__=='__main__':unittest.main()
