"""Named, immutable mechanistic specifications; no fitted website constants."""

from dataclasses import dataclass

from regsite.sequence import InputError


@dataclass(frozen=True)
class Profile:
    """A bounded folding context and a coding footprint measured from start base 0."""

    name: str
    model_id: str
    upstream_nt: int
    downstream_nt: int
    footprint_nt: int

    @property
    def historical(self) -> bool:
        return self.name == "historical"


PROFILES = (
    Profile("historical", "salis-v1-rnastructure-6.6-reconstruction-1", 35, 35, 1000),
    Profile(
        "footprint2017", "footprint2017-rnastructure-6.6-reconstruction-1", 35, 35, 13
    ),
    Profile(
        "context2017", "context2017-rnastructure-6.6-reconstruction-1", 100, 100, 13
    ),
)


def get_profile(name: str) -> Profile:
    """Resolve only published package profiles, never silently default a typo."""
    for profile in PROFILES:
        if name in (profile.name, profile.model_id):
            return profile
    raise InputError(f"unknown RBS profile: {name!r}")
