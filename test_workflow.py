"""Meaningful safety and behavior checks; no network and no third-party data."""
import copy
import json
import os
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workflow as w


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.customers, cls.quarantine, cls.audit = w.load_customers(os.environ["CUSTOMERS_PATH"])
        cls.lookup = {c["customer_id"]: c for c in cls.customers}
        cls.docs = w.load_kb(os.environ["KB_PATH"])
        cls.today = date(2026, 11, 1)

    def c(self, key="CUST_0001"):
        return copy.deepcopy(self.lookup[key])

    def test_malformed_row_quarantined(self):
        self.assertEqual(self.quarantine, [{"customer_id": "CUST_2635", "reason": "field_count", "fields": 15}])
        self.assertEqual(len(self.customers), 2999)

    def test_data_contract_findings(self):
        self.assertEqual(self.audit["asset_mismatch"], 21)
        self.assertEqual(self.audit["inactive_mismatch"], 168)
        self.assertEqual(self.audit["flagged_risk"], 8)
        self.assertEqual(self.audit["flagged_login"], 11)

    def test_boundary_assets(self):
        self.assertEqual(w.asset_band(99999.99), "长尾(<10万)")
        self.assertEqual(w.asset_band(100000), "成长(10-50万)")
        self.assertEqual(w.asset_band(500000), "富裕(50万+)")

    def test_segment_exhaustive(self):
        tail = [c for c in self.customers if c["total_assets"] < 100000]
        groups = {"基础投教服务", "理财风险解读", "基金风险解读"}
        self.assertEqual(len(tail), 405)
        self.assertTrue(all(w.segment(c) in groups for c in tail))

    def test_asset_label_does_not_override_amount(self):
        self.assertEqual(w.segment(self.c("CUST_0022")), "非长尾")

    def test_flag_conflict_is_unknown_risk(self):
        c = self.c("CUST_0999")
        self.assertEqual(c["risk_level"], "C1保守")
        self.assertTrue(c["risk_uncertain"])
        candidates = w.retrieve(c, self.docs, self.today)
        self.assertTrue(all(s["kind"] == "education" for s in candidates))

    def test_low_risk_interest_cannot_override_gate(self):
        c = self.c(); c["holding_preference"] = "ETF"; c["last_click_category"] = "市场热点"
        got = w.retrieve(c, self.docs, self.today, hotspot="AI科技热点 行业主题ETF")
        self.assertTrue(got)
        self.assertTrue(all(s["min_risk"] <= 2 for s in got))

    def test_chunk_level_fund_gate(self):
        c = self.c("CUST_0005")
        got = w.retrieve(c, self.docs, self.today)
        self.assertEqual([s["id"] for s in got], ["fund_risk"])

    def test_current_stale_sources_stop(self):
        r = w.run_one(self.c(), self.docs, self.today, mode="current")
        self.assertEqual(r["status"], "HOLD_NO_FRESH_SOURCE")
        self.assertIsNone(r["copy"])

    def test_simulation_label_and_footer(self):
        r = w.run_one(self.c(), self.docs, self.today)
        self.assertTrue(r["copy"].startswith(w.SIM_NOTE))
        self.assertTrue(r["copy"].endswith(w.DISCLAIMER))
        self.assertIn(w.PRODUCT_NOTE, r["copy"])
        self.assertFalse(r["actual_send"])
        self.assertEqual(r["status"], "REVIEW_REQUIRED")

    def test_three_actual_profiles(self):
        texts = []
        for i in ["CUST_0003", "CUST_0001", "CUST_0005"]:
            r = w.run_one(self.c(i), self.docs, self.today)
            self.assertEqual(r["status"], "REVIEW_REQUIRED")
            self.assertEqual(w.text_audit(r["copy"], self.c(i)), [])
            texts.append(r["copy"])
        self.assertEqual(len(set(texts)), 3)

    def test_minimal_profile_excludes_identifiers(self):
        p = w.minimal_profile(self.c())
        self.assertEqual(set(p), {"service_group", "risk_level", "interest", "engagement"})
        self.assertNotIn("CUST_", w.dumps(p))

    def test_model_cannot_inject_extra_text(self):
        c = self.c(); candidates = w.retrieve(c, self.docs, self.today)
        d = w.offline_decision(candidates); d["body"] = "建议买入某股票"
        self.assertEqual(w.validate_decision(d, candidates, c), ["json_schema"])

    def test_hallucinated_evidence_rejected(self):
        c = self.c(); candidates = w.retrieve(c, self.docs, self.today)
        d = w.offline_decision(candidates); d["evidence_ids"] = ["kb_99"]
        self.assertIn("evidence_mismatch", w.validate_decision(d, candidates, c))

    def test_unretrieved_risky_sentence_rejected(self):
        c = self.c(); candidates = w.retrieve(c, self.docs, self.today)
        d = {"opening_id": "etf", "sentence_ids": ["etf_risk"], "evidence_ids": ["kb_03_etf"]}
        self.assertEqual(w.validate_decision(d, candidates, c), ["unretrieved_sentence"])

    def test_schema_types_rejected(self):
        c = self.c(); candidates = w.retrieve(c, self.docs, self.today)
        for value in [None, [], {"opening_id": [], "sentence_ids": [], "evidence_ids": []}]:
            self.assertTrue(w.validate_decision(value, candidates, c))

    def test_unicode_evasion_rejected(self):
        self.assertIn("return_promise", w.text_audit("保\u200b本保息。"+w.DISCLAIMER, self.c()))
        self.assertIn("security_code", w.text_audit("关注６００５１９。"+w.DISCLAIMER, self.c()))

    def test_recommendation_and_hype_rejected(self):
        bad = "内部消息，抓紧上车，建议买入600519，指数年底必到4000点。"+w.DISCLAIMER
        errors = w.text_audit(bad, self.c())
        self.assertIn("trade_advice", errors)
        self.assertIn("inducement", errors)
        self.assertIn("security_code", errors)
        self.assertIn("point_prediction", errors)

    def test_badcase_one_legacy_misses_mixed_risk_content(self):
        text = "二是权益类基金发行边际回暖，偏股混合型基金新发份额环比增长约两成，但绝对水平仍处近年中等偏低位置；"+w.DISCLAIMER
        self.assertIn(text.removesuffix(w.DISCLAIMER), self.docs["kb_02_fund"]["text"])
        self.assertEqual(w.legacy_check(text), [])
        self.assertIn("risk_content", w.text_audit(text, self.c("CUST_0005")))

    def test_badcase_two_legacy_false_positive(self):
        text = w.CATALOG_MAP["fund_risk"]["text"] + w.PRODUCT_NOTE + w.DISCLAIMER
        self.assertEqual(w.legacy_check(text), ["keyword_block"])
        self.assertEqual(w.text_audit(text, self.c("CUST_0005")), [])

    def test_similar_negation_not_a_blanket_exemption(self):
        text = "并非所有产品都有风险，本产品保本保息。"+w.DISCLAIMER
        self.assertIn("return_promise", w.text_audit(text, self.c()))

    def test_retry_bounded_and_no_unsafe_fallback(self):
        calls = []
        def bad(messages):
            calls.append(1)
            return {"body": "建议买入"}
        r = w.run_one(self.c(), self.docs, self.today, generate=bad)
        self.assertEqual(len(calls), 2)
        self.assertEqual(r["status"], "HOLD_VALIDATION_FAILED")
        self.assertIsNone(r["copy"])

    def test_one_retry_can_recover(self):
        c = self.c(); candidates = w.retrieve(c, self.docs, self.today)
        calls = []
        def recovering(messages):
            calls.append(1)
            return {} if len(calls) == 1 else w.offline_decision(candidates)
        r = w.run_one(c, self.docs, self.today, generate=recovering)
        self.assertEqual(len(r["attempts"]), 2)
        self.assertEqual(r["status"], "REVIEW_REQUIRED")

    def test_timeout_holds_without_raw_error(self):
        def timeout(messages):
            raise TimeoutError("secret_provider_details")
        r = w.run_one(self.c(), self.docs, self.today, generate=timeout)
        self.assertEqual(r["status"], "HOLD_PROVIDER_ERROR")
        self.assertNotIn("secret_provider_details", w.dumps(r))

    def test_live_api_denied_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "allowlisted"):
                w.company_api([])

    def test_offline_never_calls_api(self):
        with patch.object(w, "company_api", side_effect=AssertionError("unexpected_network")):
            r = w.run_one(self.c(), self.docs, self.today)
            self.assertEqual(r["provider"], "offline")

    def test_no_redirects_to_other_hosts(self):
        with self.assertRaisesRegex(ValueError, "redirect_forbidden"):
            w.NoRedirect().redirect_request(None, None, 302, "found", {}, "https://other.example/")

    def test_non_target_not_generated(self):
        r = w.run_one(self.c("CUST_0002"), self.docs, self.today)
        self.assertEqual(r["status"], "SKIP_NON_TARGET")
        self.assertIsNone(r["copy"])

    def test_higher_risk_can_receive_etf_education(self):
        c = self.c("CUST_0002")
        got = w.retrieve(c, self.docs, self.today)
        self.assertEqual([s["id"] for s in got], ["etf_risk"])

    def test_three_segments_have_distinct_service_needs(self):
        counts = {g: sum(w.segment(c) == g for c in self.customers) for g in
                  ["基础投教服务", "理财风险解读", "基金风险解读"]}
        self.assertEqual(counts, {"基础投教服务": 287, "理财风险解读": 59, "基金风险解读": 59})
        self.assertEqual([w.segment(self.c(i)) for i in ["CUST_0003", "CUST_0001", "CUST_0005"]], list(counts))

    def test_every_example_has_neutral_reading_guide(self):
        for i in ["CUST_0003", "CUST_0001", "CUST_0005"]:
            r = w.run_one(self.c(i), self.docs, self.today)
            self.assertIn(w.READING_GUIDES[r["decision"]["opening_id"]], r["copy"])
            self.assertLessEqual(len(r["copy"]), 160)

    def test_low_click_activity_routes_to_basic_education(self):
        c = self.c(); c["content_click_count_30d"] = 2
        self.assertEqual(w.segment(c), "基础投教服务")
        self.assertEqual(w.target_kind(c), "education")

    def test_hotspot_cannot_bypass_lower_risk_permission(self):
        c = self.c("CUST_0005")
        r = w.run_one(c, self.docs, self.today, hotspot="AI主题 行业主题ETF")
        self.assertEqual(r["status"], "REVIEW_REQUIRED")
        self.assertEqual(r["retrieved_ids"], ["fund_risk"])
        self.assertNotIn("AI主题", r["copy"])

    def test_company_adapter_wire_contract_without_network(self):
        c = self.c(); candidates = w.retrieve(c, self.docs, self.today)
        decision = w.offline_decision(candidates)
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit):
                return json.dumps({"choices": [{"message": {"content": json.dumps(decision)}}]}).encode()
        class Opener:
            def open(self, req, timeout):
                payload = json.loads(req.data)
                assert req.full_url == "https://company.example/v1/chat/completions"
                assert timeout == 20
                assert payload["model"] == "test-model"
                assert payload["messages"][1]["role"] == "user"
                return Response()
        conf = {"COMPANY_API_URL": "https://company.example/v1/chat/completions",
                "COMPANY_APPROVED_HOST": "company.example", "COMPANY_API_AUTHORIZED": "yes",
                "COMPANY_MODEL": "test-model", "COMPANY_API_KEY": "fake-local-test-key"}
        with patch.dict(os.environ, conf, clear=True), patch.object(w, "build_opener", return_value=Opener()):
            messages = w.build_prompt(c, candidates, self.docs, "simulation")
            self.assertEqual(w.company_api(messages), decision)

    def test_local_model_missing_artifacts_holds(self):
        with patch.dict(os.environ, {"LOCAL_LLAMA_BIN": "/not-present/llama-cli", "LOCAL_MODEL_GGUF": "/not-present/model.gguf"}):
            r = w.run_one(self.c(), self.docs, self.today, provider="local")
        self.assertEqual(r["status"], "HOLD_PROVIDER_ERROR")
        self.assertIsNone(r["copy"])

    def test_local_trace_retained_and_decision_revalidated(self):
        c = self.c(); candidates = w.retrieve(c, self.docs, self.today)
        d = w.offline_decision(candidates)
        result = w.LocalModelResult(d, w.dumps(d), 1234, "test-hash")
        r = w.run_one(c, self.docs, self.today, provider="local", generate=lambda _: result)
        self.assertEqual(r["status"], "REVIEW_REQUIRED")
        self.assertEqual(r["attempts"][0]["elapsed_ms"], 1234)
        self.assertEqual(r["attempts"][0]["raw_model_response"], w.dumps(d))
        self.assertFalse(r["actual_send"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
