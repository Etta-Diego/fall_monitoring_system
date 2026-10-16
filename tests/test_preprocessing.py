import numpy as np

from fallmon.preprocessing import Scaler, StreamingPreprocessor, add_magnitudes, preprocess


def _signal(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n) / 200
    base = np.column_stack([np.sin(2 * np.pi * f * t) for f in (1, 2, 3, 0.5, 5, 40)])
    return base + 0.1 * rng.standard_normal((n, 6))


def test_streaming_matches_offline_causal(cfg):
    assert not cfg.preprocessing.offline_zero_phase
    x = _signal()
    offline = preprocess(x, cfg)
    sp = StreamingPreprocessor(cfg)
    stream = np.array([y for s in x if (y := sp.push(s)) is not None])
    np.testing.assert_allclose(stream, offline, atol=1e-10)


def test_downsampled_length_and_rate(cfg):
    x = _signal(n=2400)  # 12 s at 200 Hz
    assert preprocess(x, cfg).shape == (600, 8)  # 12 s at 50 Hz


def test_constant_signal_has_no_startup_transient(cfg):
    x = np.tile([0.0, 0.0, 1.0, 0.0, 0.0, 0.0], (800, 1))
    out = preprocess(x, cfg)
    np.testing.assert_allclose(out[:, 6], 1.0, atol=1e-9)  # Am stays at 1 g from the first sample


def test_magnitudes():
    out = add_magnitudes(np.array([[3.0, 4.0, 0.0, 0.0, 6.0, 8.0]]))
    np.testing.assert_allclose(out[0, 6:], [5.0, 10.0])


def test_scaler_roundtrip(tmp_path):
    data = np.random.default_rng(1).normal(5, 2, size=(1000, 3))
    sc = Scaler.fit(data, ["a", "b", "c"], ["SA02", "SA01"])
    z = sc.transform(data)
    np.testing.assert_allclose(z.mean(axis=0), 0, atol=1e-12)
    sc.save(tmp_path / "s.json")
    sc2 = Scaler.load(tmp_path / "s.json")
    np.testing.assert_allclose(sc2.transform(data), z)
    assert sc2.fit_subjects == ["SA01", "SA02"]
