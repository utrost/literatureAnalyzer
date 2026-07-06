"""Trope Taxonomy — curated vocabulary of 50 key literary tropes.

Used by the Trope Extractor to tag beats with consistent, searchable labels.
"""

from __future__ import annotations

from pydantic import BaseModel


class TropeDefinition(BaseModel):
    id: str
    name: str
    description: str
    category: str


TROPE_TAXONOMY: list[TropeDefinition] = [
    # --- Character Tropes ---
    TropeDefinition(
        id="tragic_flaw",
        name="Tragic Flaw",
        description="A character defect (greed, jealousy, pride) that directly causes their downfall.",
        category="character",
    ),
    TropeDefinition(
        id="reluctant_hero",
        name="Reluctant Hero",
        description="A protagonist who does not want to get involved but is forced by circumstance.",
        category="character",
    ),
    TropeDefinition(
        id="corrupted_hero",
        name="Corrupted Hero",
        description="A good character who slowly turns evil or compromised due to temptation.",
        category="character",
    ),
    TropeDefinition(
        id="anti_hero",
        name="Anti-Hero",
        description="A protagonist who lacks conventional heroic attributes, working for good via dark means.",
        category="character",
    ),
    TropeDefinition(
        id="mentor_figure",
        name="Mentor Figure",
        description="A guide or father figure who establishes the hero's path and often departs early.",
        category="character",
    ),
    TropeDefinition(
        id="doppelganger",
        name="Doppelganger",
        description="A double or alter ego representing a split personality or hidden desires.",
        category="character",
    ),
    TropeDefinition(
        id="femme_fatale",
        name="Femme Fatale",
        description="An alluring but dangerous character who leads the protagonist into peril.",
        category="character",
    ),
    TropeDefinition(
        id="mad_scientist",
        name="Mad Scientist",
        description="A creator obsessed with knowledge or power, crossing ethical/natural boundaries.",
        category="character",
    ),
    TropeDefinition(
        id="secret_identity",
        name="Secret Identity",
        description="A character hiding their true identity to protect themselves or execute a plan.",
        category="character",
    ),
    TropeDefinition(
        id="nemesis",
        name="Nemesis",
        description="A dedicated rival or enemy whose fate is bound to the protagonist's.",
        category="character",
    ),

    # --- Plot / Narrative Tropes ---
    TropeDefinition(
        id="faustian_bargain",
        name="Faustian Bargain",
        description="A deal with a powerful/sinister force for personal gain, carrying a heavy toll.",
        category="plot",
    ),
    TropeDefinition(
        id="noble_sacrifice",
        name="Noble Sacrifice",
        description="Giving up one's life, happiness, or prized possession for the sake of another.",
        category="plot",
    ),
    TropeDefinition(
        id="unreliable_narrator",
        name="Unreliable Narrator",
        description="A narrator whose credibility is compromised, intentionally or unintentionally misleading the reader.",
        category="plot",
    ),
    TropeDefinition(
        id="race_against_time",
        name="Race Against Time",
        description="A story driven by an urgent deadline or ticking clock.",
        category="plot",
    ),
    TropeDefinition(
        id="locked_room",
        name="Locked Room",
        description="A conflict taking place in an isolated, escape-proof, or inaccessible location.",
        category="plot",
    ),
    TropeDefinition(
        id="mistaken_identity",
        name="Mistaken Identity",
        description="Confusion of a character's true identity, causing drama or complications.",
        category="plot",
    ),
    TropeDefinition(
        id="forbidden_love",
        name="Forbidden Love",
        description="Romance prevented by society, family rivalry, or duty.",
        category="plot",
    ),
    TropeDefinition(
        id="revenge_quest",
        name="Revenge Quest",
        description="A journey motivated entirely by avenging a past insult, injury, or death.",
        category="plot",
    ),
    TropeDefinition(
        id="fall_from_grace",
        name="Fall from Grace",
        description="A high-status or moral character losing their standing, sanity, or integrity.",
        category="plot",
    ),
    TropeDefinition(
        id="reluctant_alliance",
        name="Reluctant Alliance",
        description="Enemies or opposites forced to work together to survive.",
        category="plot",
    ),
    TropeDefinition(
        id="betrayal",
        name="Betrayal",
        description="A trusted ally breaks faith, shifting the balance of conflict.",
        category="plot",
    ),
    TropeDefinition(
        id="prophecy",
        name="Prophecy",
        description="A prediction of future events that characters try to fulfill or escape.",
        category="plot",
    ),
    TropeDefinition(
        id="chosen_one",
        name="Chosen One",
        description="A character destined by fate or bloodline to resolve the central conflict.",
        category="plot",
    ),
    TropeDefinition(
        id="poetic_justice",
        name="Poetic Justice",
        description="An ironic twist where characters get exactly what they deserve, matching their deeds.",
        category="plot",
    ),
    TropeDefinition(
        id="deus_ex_machina",
        name="Deus Ex Machina",
        description="An unexpected, sudden resolution to an otherwise unsolvable problem.",
        category="plot",
    ),
    TropeDefinition(
        id="cat_and_mouse",
        name="Cat and Mouse",
        description="A tense game of pursuit and evasion between two clever opponents.",
        category="plot",
    ),
    TropeDefinition(
        id="divided_allegiance",
        name="Divided Allegiance",
        description="A character caught between conflicting duties, loyalties, or laws.",
        category="plot",
    ),
    TropeDefinition(
        id="dark_night_of_the_soul",
        name="Dark Night of the Soul",
        description="The lowest point of despair and isolation before a turning point.",
        category="plot",
    ),
    TropeDefinition(
        id="temptation",
        name="Temptation",
        description="An offer of quick gain or escape that tests a character's morals.",
        category="plot",
    ),
    TropeDefinition(
        id="unrequited_love",
        name="Unrequited Love",
        description="Love that is not returned, causing longing and sorrow.",
        category="plot",
    ),
    TropeDefinition(
        id="pyrrhic_victory",
        name="Pyrrhic Victory",
        description="A win that comes at such a high cost it feels like a defeat.",
        category="plot",
    ),
    TropeDefinition(
        id="warning_ignored",
        name="Warning Ignored",
        description="A clear warning about danger that characters dismiss to their peril.",
        category="plot",
    ),
    TropeDefinition(
        id="forbidden_knowledge",
        name="Forbidden Knowledge",
        description="Seeking secrets of the universe, science, or magic that should remain hidden.",
        category="plot",
    ),
    TropeDefinition(
        id="return_from_the_grave",
        name="Return from the Grave",
        description="The literal or metaphorical return of someone believed dead.",
        category="plot",
    ),
    TropeDefinition(
        id="sanity_slipping",
        name="Sanity Slipping",
        description="A character slowly losing their grip on reality due to isolation or terror.",
        category="plot",
    ),
    TropeDefinition(
        id="broken_vow",
        name="Broken Vow",
        description="A broken promise or oath that triggers a curse or conflict.",
        category="plot",
    ),
    TropeDefinition(
        id="usurper",
        name="Usurper",
        description="A rival who takes power, status, or inheritance that belongs to another.",
        category="plot",
    ),

    # --- Setting / World Tropes ---
    TropeDefinition(
        id="haunted_house",
        name="Haunted House",
        description="A setting that holds memories, ghosts, or curses of the past.",
        category="setting",
    ),
    TropeDefinition(
        id="dystopia",
        name="Dystopia",
        description="A society characterized by oppression, control, and misery.",
        category="setting",
    ),
    TropeDefinition(
        id="gothic_decay",
        name="Gothic Decay",
        description="A setting or atmosphere of ruin, ancient curses, and dark secrets.",
        category="setting",
    ),
    TropeDefinition(
        id="liminal_space",
        name="Liminal Space",
        description="A place representing transition, thresholds, or edges of reality (e.g. lighthouses, boundaries).",
        category="setting",
    ),
    TropeDefinition(
        id="microcosm",
        name="Microcosm",
        description="A small, representative system having analogies to a larger world.",
        category="setting",
    ),
    TropeDefinition(
        id="ruined_kingdom",
        name="Ruined Kingdom",
        description="A setting that was once prosperous but has fallen to ruin and neglect.",
        category="setting",
    ),

    # --- Symbolic / Object Tropes ---
    TropeDefinition(
        id="macguffin",
        name="MacGuffin",
        description="An object or goal that characters pursue, serving as the primary plot driver.",
        category="object",
    ),
    TropeDefinition(
        id="cursed_object",
        name="Cursed Object",
        description="An item that brings misfortune, tragedy, or madness to its owner.",
        category="object",
    ),
    TropeDefinition(
        id="chekhovs_gun",
        name="Chekhov's Gun",
        description="An insignificant object introduced early that becomes crucial to the climax.",
        category="object",
    ),
    TropeDefinition(
        id="memento_mori",
        name="Memento Mori",
        description="Symbolic reminders of mortality (e.g. skulls, ticking clocks, failing health).",
        category="object",
    ),
    TropeDefinition(
        id="red_herring",
        name="Red Herring",
        description="A false clue meant to distract characters and readers from the truth.",
        category="object",
    ),
]


def format_taxonomy_for_prompt() -> str:
    """Format the trope taxonomy as a readable list for LLM prompts."""
    lines = []
    for t in TROPE_TAXONOMY:
        lines.append(f"- `{t.id}`: {t.name} - {t.description} ({t.category})")
    return "\n".join(lines)
