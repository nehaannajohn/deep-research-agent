from dra.schemas import Passage
from experiments.code.decomposition_retrieval import unique_source_ids, overlap_stats


def test_unique_source_ids_collects_across_passages():
    passages = [Passage(source_id="s1", text="a"), Passage(source_id="s2", text="b"),
                Passage(source_id="s1", text="c")]
    assert unique_source_ids(passages) == {"s1", "s2"}


def test_overlap_stats_counts_and_jaccard():
    st = overlap_stats({"s1", "s2", "s3"}, {"s2", "s3", "s4"})
    assert st["only_a"] == 1
    assert st["only_b"] == 1
    assert st["shared"] == 2
    assert abs(st["jaccard"] - 0.5) < 1e-9


def test_overlap_stats_handles_empty():
    st = overlap_stats(set(), set())
    assert st["shared"] == 0 and st["jaccard"] == 0.0
