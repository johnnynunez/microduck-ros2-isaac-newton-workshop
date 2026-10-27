"""Translate untrusted gateway data; never forward arbitrary receipt fields."""

from microduck_workshop.contracts import MAX_SENSOR_AGE_S, ContractError, finite_number, identifier


def translate_observation(raw, *, episode_id, frame_id, round_trip_s=0.0):
    """Use capture age plus full RPC latency; text reasons are deliberately discarded."""
    try:
        episode = identifier(raw["episode_id"], "episode_id")
        if episode != episode_id or raw["frame_id"] != frame_id:
            raise ContractError("foreign_observation")
        for name in ("generation", "frame_sequence"):
            if type(raw[name]) is not int or raw[name] < 0:
                raise ContractError("invalid_observation")
        age = finite_number(raw["age_s"], "age_s")
        trip = finite_number(round_trip_s, "round_trip_s")
        sim_time = finite_number(raw["sim_time"], "sim_time")
        if age < 0 or trip < 0 or sim_time < 0:
            raise ContractError("invalid_observation")
        tags = raw["tag_ids"]
        if (
            not isinstance(tags, (list, tuple))
            or len(tags) > 256
            or any(type(tag) is not int or not 0 <= tag <= 586 for tag in tags)
        ):
            raise ContractError("invalid_observation")
        age += trip
        fresh = raw["fresh"] is True and age <= MAX_SENSOR_AGE_S
        tags = sorted(set(tags)) if fresh else []
        signal = "STOP" if 1 in tags else "GO" if 0 in tags else "UNKNOWN"
        return dict(
            ok=fresh,
            fresh=fresh,
            episode_id=episode,
            generation=raw["generation"],
            frame_sequence=raw["frame_sequence"],
            sim_time=sim_time,
            age_s=age,
            frame_id=frame_id,
            tag_ids=tags,
            signal=signal,
            reason="sensor_observation" if fresh else "stale_observation",
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return dict(
            ok=False, fresh=False, signal="UNKNOWN", reason="invalid_or_foreign_observation"
        )
