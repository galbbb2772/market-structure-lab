import math
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from structure_core import validate_bars, detect_boxes, box_scores, sector_activity, news_tension, updown_stats, nonoverlap_forward_rates


def make_bars(n=450, break_at=None):
    bars=[]
    for i in range(n):
        p=100+3.5*math.sin(i*math.pi/5)
        if break_at is not None and i>=break_at: p=145+3.5*math.sin(i*.2)
        d=(date(2020,1,1)+timedelta(days=i)).isoformat()
        bars.append([d,p,p+1,p-1,p,100000+i*100])
    return bars

class StructureTests(unittest.TestCase):
    def test_sanitization_and_sorted(self):
        b=make_bars(3); r=validate_bars([b[2],b[0],b[1],b[1]])
        self.assertEqual(len(r),3); self.assertEqual(r[0][0],b[0][0])
    def test_online_box_prefix_invariance(self):
        full=make_bars(170,120); first=detect_boxes(full[:100],20,.14); later=detect_boxes(full,20,.14)
        self.assertTrue(first); self.assertEqual(first[0]['detected_at'],later[0]['detected_at']); self.assertEqual(first[0]['upper'],later[0]['upper'])
    def test_monotonic_drift_filter(self):
        b=[]
        for i in range(70):
            p=110-i*.5; b.append([(date(2020,1,1)+timedelta(days=i)).isoformat(),p,p+.2,p-.2,p,1000])
        self.assertEqual(detect_boxes(b,20,.14),[])
    def test_scoring_ranges(self):
        self.assertTrue(all(0<=v<=10 for v in box_scores(make_bars(100),0,40,95,105).values()))
    def test_activity(self):
        a=sector_activity(make_bars(120)); self.assertEqual(a['status'],'ok'); self.assertTrue(0<=a['activity']<=100)
    def test_news_no_backfill(self):
        b=make_bars(6); keys=('us_policy_event_sentiment','geopolitical_news_risk','systemic_news_risk','ai_narrative_risk','negative_narrative_density')
        d={'history':[{'date':b[-1][0],'reaction_adjusted':{k:20 for k in keys}}]}; v=news_tension(d,{'sp500':b})
        self.assertEqual(v[0]['tension'],20)
    def test_forward_cutoff(self):
        b=make_bars(450); a=nonoverlap_forward_rates(b,b[300][0],20); c=nonoverlap_forward_rates(b,b[350][0],20); self.assertLessEqual(a['n'],c['n'])
    def test_updown(self):
        s=updown_stats(make_bars(100)); self.assertEqual(s['n'],99); self.assertIsNotNone(s['up_median_pct']); self.assertIsNotNone(s['down_median_pct'])

if __name__ == '__main__': unittest.main()
