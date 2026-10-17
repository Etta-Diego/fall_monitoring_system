import numpy as np
import torch

from fallmon.dte import CNN1D, DeepTimeEnsemble
from fallmon.ood import confidence, is_ood, threshold_at_tpr


def test_cnn_output_shape_for_each_window_length():
    m = CNN1D(8, 15, 0.3).eval()
    for length in (50, 100, 150):
        assert m(torch.zeros(4, 8, length)).shape == (4, 15)


def test_ensemble_probabilities_and_save_load(tmp_path):
    torch.manual_seed(0)
    models = [CNN1D(8, 3, 0.3) for _ in range(3)]
    ens = DeepTimeEnsemble(models, [50, 100, 150], ["A", "B", "C"])
    x = np.random.default_rng(0).standard_normal((400, 8))
    ends = np.array([150, 175, 400])
    p, per = ens.predict_steps(x, ends)
    assert p.shape == (3, 3) and per.shape == (3, 3, 3)
    np.testing.assert_allclose(p.sum(axis=1), 1, atol=1e-6)
    np.testing.assert_allclose(p, per.mean(axis=0))
    meta = {"classes": ["A", "B", "C"], "window_lengths_s": [1.0, 2.0, 3.0], "window_samples": [50, 100, 150],
            "channels": list("abcdefgh"), "dropout": 0.3}
    ens.save(tmp_path, [1.0, 2.0, 3.0], meta)
    ens2, _ = DeepTimeEnsemble.load(tmp_path)
    np.testing.assert_allclose(ens2.predict_steps(x, ends)[0], p, atol=1e-6)


def test_ood_rules():
    p = np.array([[0.95, 0.05], [0.6, 0.4]])
    np.testing.assert_allclose(confidence(p), [0.95, 0.6])
    np.testing.assert_array_equal(is_ood(confidence(p), 0.9), [False, True])
    assert abs(threshold_at_tpr(np.linspace(0, 1, 101), 0.95) - 0.05) < 1e-9
