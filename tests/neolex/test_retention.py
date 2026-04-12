"""Tests for neolex.compliance.retention (SOC 2 data retention policy)."""

import datetime

from neolex.compliance.retention import DEFAULT_RETENTION_DAYS, RetentionPolicy


def test_default_retention_days(monkeypatch):
    monkeypatch.delenv("AUDIT_LOG_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.retention_days == DEFAULT_RETENTION_DAYS
    assert policy.retention_days == 90


def test_custom_retention_days(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "90")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.retention_days == 90


def test_observation_period_blocks_purge(monkeypatch):
    monkeypatch.setenv("SOC2_OBSERVATION_PERIOD", "true")
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    policy = RetentionPolicy()
    assert policy.observation_period_active is True
    assert policy.purge_allowed is False


def test_zero_retention_blocks_purge(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "0")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.purge_allowed is False


def test_normal_config_allows_purge(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    assert policy.purge_allowed is True


def test_cutoff_date_is_in_past(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "365")
    monkeypatch.delenv("SOC2_OBSERVATION_PERIOD", raising=False)
    policy = RetentionPolicy()
    cutoff = policy.cutoff_date
    assert cutoff < datetime.datetime.now(datetime.UTC)
    expected = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=365)
    diff = abs((cutoff - expected).total_seconds())
    assert diff < 5


# SQLite-based integration tests removed — audit DB migrated to PostgreSQL.
