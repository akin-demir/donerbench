from __future__ import annotations

from statistics import mean, pstdev

from donerbench.schemas import SliceMetrics


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_run(slices: list[SliceMetrics], total_attempts: int) -> tuple[float, dict[str, float], str]:
    if not slices:
        components = {
            "average_slice_quality": 0.0,
            "uniformity_score": 0.0,
            "freshness_score": 0.0,
            "valid_slice_count_score": 0.0,
            "low_waste_score": 0.0,
            "low_tear_score": 0.0,
            "speed_score": 0.0,
        }
        return 0.0, components, "No service"

    valid_slices = [slice_ for slice_ in slices if slice_.valid]
    quality_source = valid_slices or slices
    target_attempts = max(1, total_attempts)

    average_slice_quality = mean(slice_.slice_score for slice_ in quality_source)
    uniformity_score = _uniformity_component(quality_source)
    freshness_score = mean(slice_.freshness_score for slice_ in quality_source)
    # Every attempt should land a valid slice; throughput rewards attempts that cut.
    valid_slice_count_score = clamp((len(valid_slices) / target_attempts) * 100.0)
    low_waste_score = clamp(100.0 - mean(slice_.waste_penalty for slice_ in slices))
    low_tear_score = clamp(100.0 - mean(slice_.tear_penalty for slice_ in slices))
    speed_score = clamp((len(slices) / target_attempts) * 100.0)

    components = {
        "average_slice_quality": average_slice_quality,
        "uniformity_score": uniformity_score,
        "freshness_score": freshness_score,
        "valid_slice_count_score": valid_slice_count_score,
        "low_waste_score": low_waste_score,
        "low_tear_score": low_tear_score,
        "speed_score": speed_score,
    }
    final_score = (
        0.25 * average_slice_quality
        + 0.20 * uniformity_score
        + 0.15 * freshness_score
        + 0.15 * valid_slice_count_score
        + 0.10 * low_waste_score
        + 0.10 * low_tear_score
        + 0.05 * speed_score
    )
    return round(clamp(final_score), 2), {key: round(value, 2) for key, value in components.items()}, _verdict(slices, components)


def _uniformity_component(slices: list[SliceMetrics]) -> float:
    if len(slices) <= 1:
        return slices[0].uniformity_score if slices else 0.0
    thicknesses = [slice_.thickness_mm for slice_ in slices]
    spread_penalty = pstdev(thicknesses) * 18.0
    local_uniformity = mean(slice_.uniformity_score for slice_ in slices)
    return clamp((local_uniformity * 0.65) + ((100.0 - spread_penalty) * 0.35))


def _verdict(slices: list[SliceMetrics], components: dict[str, float]) -> str:
    average_thickness = mean(slice_.thickness_mm for slice_ in slices)
    average_waste = mean(slice_.waste_penalty for slice_ in slices)
    average_tear = mean(slice_.tear_penalty for slice_ in slices)

    if components["average_slice_quality"] > 88 and components["speed_score"] > 45:
        return "Perfect service"
    if components["average_slice_quality"] > 82 and components["speed_score"] <= 45:
        return "Excellent but slow"
    if average_waste > 30:
        return "Fast but wasteful"
    if average_thickness > 7.5:
        return "Too thick"
    if average_tear > 32:
        return "Too aggressive"
    if components["uniformity_score"] < 62:
        return "Inconsistent slicing"
    return "Clean service"
