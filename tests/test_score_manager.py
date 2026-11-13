import pytest

from syllable_shaker.ScoreManager import ScoreManager


def test_new_manager_fail():
    with pytest.raises(TypeError):
        ScoreManager()


@pytest.mark.parametrize("input_score", [(""), ("1"), ("1.2"), ("1:2:3"), ("1:2.3")])
def test_new_manager_bad_format(input_score):
    with pytest.raises(Exception):
        ScoreManager(input_score)


@pytest.mark.parametrize("input_score", [("1:2"), ("3:0")])
def test_new_manager_success(input_score):
    manager = ScoreManager(input_score)
    assert manager is not None


def test_score_rountrip():
    score = "1:2"
    manager = ScoreManager(score)
    assert manager.GetScore() == score


def test_success():
    score = "0:0"
    manager = ScoreManager(score)
    manager.Succeeded()
    assert manager.Success == 1
    assert manager.Fails == 0


def test_failure():
    score = "0:0"
    manager = ScoreManager(score)
    manager.Failed()
    assert manager.Success == 0
    assert manager.Fails == 1


def test_full_journey():
    score = "3:1"
    manager = ScoreManager(score)
    manager.Failed()
    manager.Succeeded()
    manager.Succeeded()
    assert manager.Success == 3
    assert manager.Fails == 4
