# 2026 World Cup Tournament Context Pack

Generated for WorldCupArena tournament-level prediction prompts on 2026-06-09. This pack is injected only for S1/non-search models. S2/search models are prompted to verify current news themselves.

## Tournament format and schedule

- 48 teams play in 12 groups of four.
- The top two in every group and the eight best third-placed teams advance to a 32-team knockout stage.
- Group stage runs June 11-27, 2026; knockout stage runs June 28-July 19, ending with the final at MetLife Stadium in East Rutherford, New Jersey.
- Knockout matches are played to a finish: extra time and then penalties if needed.

## Current competitive context

- Commonly cited title contenders in preview coverage include Spain, France, Brazil, England, Argentina, Portugal, Germany and the Netherlands. Treat this as broad market/analyst prior, not a result guarantee.
- The expanded format makes third-place qualification important: models should not over-penalize one narrow group-stage loss, because eight of twelve third-placed teams still advance.
- Golden Boot previews emphasize team path length as much as finishing talent. Kylian Mbappé, Harry Kane, Erling Haaland, Vinícius Júnior, Lionel Messi and Cristiano Ronaldo are the most obvious high-profile names; value picks in recent coverage include Michael Olise, Jeremy Doku and Brazil attackers.
- Young-player previews highlight Lamine Yamal, Endrick, Arda Güler, João Neves, Désiré Doué, Pau Cubarsí and Warren Zaïre-Emery as tournament-impact players.
- Injury/news tracker notes to account for before making predictions: Lionel Messi has been managing a muscle issue but is expected to be involved; Lamine Yamal is expected to be fit for Spain's opener; Neymar has a calf issue after his Brazil recall; Alphonso Davies is a concern for Canada's opener; Jurrien Timber has withdrawn from the Netherlands squad; Germany's Lennart Karl has been ruled out with a muscle injury.

## Groups

- Group A: Mexico, South Africa, South Korea, Czech Republic
- Group B: Canada, Bosnia and Herzegovina, Qatar, Switzerland
- Group C: Brazil, Morocco, Haiti, Scotland
- Group D: United States, Paraguay, Australia, Turkey
- Group E: Germany, Curaçao, Ivory Coast, Ecuador
- Group F: Netherlands, Japan, Sweden, Tunisia
- Group G: Belgium, Egypt, Iran, New Zealand
- Group H: Spain, Cape Verde, Saudi Arabia, Uruguay
- Group I: France, Senegal, Iraq, Norway
- Group J: Argentina, Algeria, Austria, Jordan
- Group K: Portugal, DR Congo, Uzbekistan, Colombia
- Group L: England, Croatia, Ghana, Panama

## Modeling guidance for S1 models

- Use this pack plus the full fixture/spec JSON in the prompt. Do not invent unavailable late-breaking injuries.
- Predict conservatively: group-stage draws are common; knockout winners must be explicit even when the score is level before penalties.
- Use player names in structured scorer fields in their common English/official form. Chinese explanation can include bilingual names.

## Sources consulted

- FIFA official tournament page: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026
- 2026 FIFA World Cup knockout stage: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage
- 2026 FIFA World Cup group pages A-L: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_A through _Group_L
- The Guardian beginner guide, 2026-06-09: https://www.theguardian.com/football/2026/jun/09/a-very-beginners-guide-to-the-world-cup-how-does-it-work-and-the-players-to-look-out-for
- The Guardian Socceroos path guide, 2026-06-09: https://www.theguardian.com/football/2026/jun/09/socceroos-world-cup-who-stands-in-australia-way-football
- Times of India young players guide, 2026-06-09: https://timesofindia.indiatimes.com/sports/football/fifa-world-cup/yamal-endrick-guler-co-the-young-guns-ready-to-storm-fifa-world-cup-2026/articleshow/131591795.cms
- New York Post Golden Boot preview, 2026-06-09: https://nypost.com/2026/06/09/betting/2026-world-cup-golden-boot-picks-best-bets-predictions-to-score-the-most-goals/
- talkSPORT injury tracker, 2026-06-09: https://talksport.com/football/world-cup/4311921/world-cup-2026-injury-tracker-full-squads-messi/
- Bavarian Football Works Germany injury note, 2026-06-09: https://www.bavarianfootballworks.com/fifa-world-cup/212659/deniz-undav-reveals-how-lennart-karl-got-injured-in-germany-training
- The Sun Netherlands injury note, 2026-06-09: https://www.thesun.ie/sport/17079979/jurrien-timber-injury-withdraws-netherlands-world-cup-squad/
