"""Social Media access — consent-gated social signals for recommendation.

Covers: contract/backward-compat, consent gating, text weighting, the mock
connector, profile integration, and the per-item reason string.
"""
from recommend.schemas import UserContext, SocialProfile
from recommend.social import extract_social_text, social_interest_terms, connect
from recommend.profile import assemble_profile_text
from recommend.config import SOCIAL


def _social_user(**soc):
    return UserContext(user_id="x", social=SocialProfile(**soc))


class TestSocialContract:
    def test_backward_compat_user_without_social(self):
        """Old payloads (no 'social') still parse — feature is additive."""
        u = UserContext.from_dict({"user_id": "x"})
        assert isinstance(u.social, SocialProfile)
        assert u.social.consent is False
        assert u.social.active is False

    def test_parse_social(self):
        u = UserContext.from_dict({"user_id": "x",
                                   "social": {"consent": True, "follows": ["Nike"]}})
        assert u.social.consent and u.social.follows == ["Nike"] and u.social.active

    def test_consent_false_is_inactive(self):
        u = UserContext.from_dict({"user_id": "x",
                                   "social": {"consent": False, "follows": ["Nike"]}})
        assert u.social.active is False

    def test_consent_true_but_empty_is_inactive(self):
        u = UserContext.from_dict({"user_id": "x", "social": {"consent": True}})
        assert u.social.active is False

    def test_tolerates_extra_fields(self):
        sp = SocialProfile.from_dict({"consent": True, "follows": ["a"], "bogus": 1})
        assert sp.follows == ["a"]


class TestSocialText:
    def test_empty_without_consent(self):
        assert extract_social_text(_social_user(consent=False, follows=["Nike"])) == ""

    def test_weighting_follows_over_topics(self):
        t = extract_social_text(_social_user(consent=True, follows=["Nike"], topics=["running"]))
        assert t.split().count("Nike") == SOCIAL.follows_weight
        assert "running" in t

    def test_terms_consent_gated(self):
        assert social_interest_terms(_social_user(consent=False, follows=["Nike"])) == set()
        terms = social_interest_terms(_social_user(consent=True, topics=["trail running"]))
        assert {"trail", "running"} <= terms

    def test_short_tokens_dropped(self):
        terms = social_interest_terms(_social_user(consent=True, follows=["a x", "Nike"]))
        assert "nike" in terms and "a" not in terms and "x" not in terms


class TestMockConnector:
    def test_connect_requires_consent(self):
        assert connect("u", {"follows": ["Nike"]}, consent=False).active is False

    def test_connect_with_consent(self):
        p = connect("u", {"follows": ["Nike"]}, consent=True)
        assert p.consent and p.follows == ["Nike"] and p.active


class TestProfileIntegration:
    def test_social_adds_interest_text(self):
        base = UserContext(user_id="x", searches=["coffee"])
        soc = UserContext(user_id="x", searches=["coffee"],
                          social=SocialProfile(consent=True, follows=["Nike"], topics=["running"]))
        pb, ps = assemble_profile_text(base), assemble_profile_text(soc)
        assert "Nike" in ps and "Nike" not in pb
        assert len(ps) > len(pb)

    def test_no_consent_no_profile_change(self):
        base = UserContext(user_id="x", searches=["coffee"])
        soc = UserContext(user_id="x", searches=["coffee"],
                          social=SocialProfile(consent=False, follows=["Nike"]))
        assert assemble_profile_text(base) == assemble_profile_text(soc)


class TestSocialReason:
    """Reason matching is substring-based on catalog text — independent of embeddings."""

    def _rec(self):
        from recommend.pipeline import Recommender
        sku_text = {"SKU-RUN": "Nike running shoes", "SKU-MUG": "ceramic coffee mug"}
        return Recommender(sku_text, cards={})

    def test_social_reason_present_with_consent(self):
        rec = self._rec()
        u = UserContext(user_id="x",
                        social=SocialProfile(consent=True, follows=["Nike"], topics=["running"]))
        feed = rec.recommend(u, k=2)
        run = next(i for i in feed.items if i.sku_id == "SKU-RUN")
        mug = next(i for i in feed.items if i.sku_id == "SKU-MUG")
        assert "matches your social interests" in run.reasons
        assert "matches your social interests" not in mug.reasons

    def test_social_reason_absent_without_consent(self):
        rec = self._rec()
        u = UserContext(user_id="x",
                        social=SocialProfile(consent=False, follows=["Nike"], topics=["running"]))
        feed = rec.recommend(u, k=2)
        for item in feed.items:
            assert "matches your social interests" not in item.reasons
