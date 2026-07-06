# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Default example categories. These are intentionally neutral and do not contain
# real names; users can edit or replace them in the GUI.

from __future__ import annotations

from .models import CategoryConfig


def default_categories() -> list[CategoryConfig]:
    return [
        CategoryConfig(
            name="Brautpaar",
            min_per_card=1,
            max_per_card=1,
            use_as_filler=False,
            questions=[
                "dem Brautpaar beim Umzug geholfen hat",
                "mit dem Brautpaar schon im Urlaub war",
                "mit dem Brautpaar verwandt ist",
                "schneller schwimmt als die Braut",
                "das Brautpaar schon einmal zum Essen eingeladen hat",
                "schon einmal von der beruflichen Expertise der Braut beraten wurde",
                "mit der Braut oder dem Bräutigam schon einmal im selben Verein oder Team aktiv war",
                "mit dem Bräutigam schon einmal im Stadion war",
                "mit dem Bräutigam schon einmal über die beste Schnitzel-Panade philosophiert hat",
                "die Braut länger als den Bräutigam kennt",
                "den Bräutigam länger als die Braut kennt",
                "mit dem Brautpaar den Ausblick von einem Gipfel genossen hat",
                "den Bräutigam schon mal mit Süßigkeiten bestochen hat",
            ],
        ),
        CategoryConfig(
            name="EDU",
            min_per_card=0,
            max_per_card=1,
            use_as_filler=False,
            questions=[
                "die Braut aus dem Kindergarten kennt",
                "den Bräutigam aus dem Kindergarten kennt",
                "mit der Braut zur Schule ging",
                "mit dem Bräutigam zur Schule ging",
                "mit der Braut studiert hat",
            ],
        ),
        CategoryConfig(
            name="Allgemein",
            min_per_card=0,
            max_per_card=None,
            use_as_filler=True,
            questions=[
                "traditionellen Walzer tanzen kann",
                "ein Musikinstrument spielen kann",
                "Nutella unbedingt mit Butter isst",
                "vor 6:00 Uhr morgens aufsteht",
                "zwei oder mehr Kinder hat",
                "im selben Monat wie du Geburtstag hat",
                "gerne Gesellschaftsspiele spielt",
                "Pizza mit Ananas bestellt",
                "schon einmal ein wildes Tier fotografiert hat",
                "gerne unter der Dusche singt",
                "einen Zauberwürfel lösen kann",
                "ein Tattoo hat",
                "schon einmal in Afrika war",
                "Single ist",
                "dieses Jahr schon am Meer war",
                "gerne Urlaub in den Bergen macht",
                "mehr als zwei Geschwister hat",
                "dieses Jahr einen runden Geburtstag feiert",
                "gerne wandert oder klettert",
                "schon einmal auf einem anderen Kontinent gelebt hat",
                "heute bereits heimlich Schuhe gewechselt hat",
                "seine Pommes rot-weiß isst",
                "kein eigenes Auto besitzt",
                "ein Haustier besitzt",
                "Linkshänder ist",
                "aktiv in einem Verein ist",
                "dieses Jahr auf einem Festival war",
                "beim Wecker mindestens 3x auf Snooze drückt",
                "Kaffee am liebsten schwarz trinkt",
                "Katzen lieber als Hunde mag",
                "schon einmal einen Prominenten getroffen hat",
                "mehr als fünf Reisepass-Stempel hat",
                "denselben Sportverein mag wie du",
                "schon über 25 Jahre verheiratet ist",
                "aus einem anderen Land/Bundesland angereist ist",
                "schon im Fernsehen zu sehen war",
                "mehr als drei Kontinente bereist hat",
                "mehr als zwei Sprachen spricht",
                "den Moonwalk beherrscht",
                "sofort Karaoke singen würde",
                "im selben Jahr wie du geboren ist",
                "mit dem Fahrrad zur Arbeit fährt",
                "schon einmal einen Brautstrauß gefangen hat",
                "denselben Anfangsbuchstaben im Namen hat wie du",
                "dasselbe Sternzeichen wie du hat",
                "mehr als zweimal die Woche zum Sport geht",
            ],
        ),
    ]
