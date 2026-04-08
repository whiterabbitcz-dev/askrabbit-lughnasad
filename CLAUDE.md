# askrabbit-lughnasad

AskRabbit instance pro festival Lughnasad (keltský hudební festival v Nasavrkách).
Součást produktové řady **AskRabbit — Digital Concierge by White Rabbit**.

Forkováno z `wr-chatbot-template` (kanonický BeerBot base). Drží se stejné
architektury a patternu jako BeerBot pro Czech Beer Museum Prague.

---

## Persona

**Diviciacus** — druid kmene Aeduů, strážce vědění, průvodce festivalem.

- Jazyky: CZ (primární), EN, SK
- Tyká návštěvníkovi (festivalové prostředí)
- Tón: důstojný, mírně archaický, ale srozumitelný; poetický, ne akademický
- Délka odpovědí: vyprávění se skrytou informací, ne holá data
- Hluboká doména: program festivalu, kapely, keltská kultura, historie Nasavrk, praktické info (doprava, kemp, jídlo)
- Mimo doménu: zdravotní rady, politika, cokoliv mimo festival → elegantně odkáže na info stánek

System prompt žije v `config.json` (ne natvrdo v kódu), ať ho mohu editovat bez deploye.

---

## Architektura (drží se BeerBot patternu — neodchylovat se)

- **Jeden repo**, backend i frontend pohromadě
- FastAPI (Python 3.12) + uvicorn, deploy přes Dockerfile
- `server.py` = backend, `templates/index.html` + `templates/widget.js` = frontend
- `config.json` = branding (barvy, font, logo, jazyky, system prompt) — čte se přes `/config.js` endpoint, žádný build
- Knowledge base = Google Sheet, auto-refresh každých 5 minut (`KB_REFRESH_SECONDS=300`)
- Sloupce KB: A = kategorie, B = obsah
- `/admin?p=PASSWORD` dashboard s logy + tlačítko Refresh KB
- **Unanswered loop**: když odpověď obsahuje markery z `UNKNOWN_MARKERS` (server.py ~ř. 170), zapíše dotaz do tabu "Unanswered" ve stejném Sheetu
- Rate limit: in-memory (stačí 1 instance)

## Endpointy

- `GET /` — fullscreen chat (pro QR kódy)
- `GET /widget.js` — floating bubble widget pro embed
- `GET /config.js` — branding do frontendu
- `POST /chat` — hlavní chat endpoint
- `GET /health` — {api, sheets, kb_entries}
- `GET /admin?p=...` — dashboard
- `POST /kb/refresh?p=...` — force refresh KB

---

## Deployment (per-klient izolace)

- **Railway projekt**: `askrabbit-lughnasad-production` (nový, ne sdílený s BeerBotem)
- **Anthropic workspace**: `askrabbit-lughnasad-production` (nový, kvůli samostatnému billingu)
- **Google Sheet**: nový, sdílet s existujícím service accountem `beerbot-sheets@wr-chatbots-...iam.gserviceaccount.com` (SA je sdílený mezi klienty, nedělat nový)
- **Env vars na Railway**: `ANTHROPIC_API_KEY`, `GOOGLE_SHEET_ID`, `GOOGLE_SA_JSON_CONTENT`, `ADMIN_PASSWORD`
- **Auto-deploy**: push na `main` → Railway redeploy

## UI v embedu u klienta

Tlačítko / widget: **"Zeptej se Diviciaca"** (ne "Ask Rabbit" — slovo "Rabbit" návštěvník festivalu nikdy nevidí, to je interní produktový název agentury).

---

## Pravidla pro práci na tomto projektu

1. **Držet se BeerBot architektury.** Pokud něco nedává smysl nebo by se dalo elegantněji — nejdřív řekni, pak navrhni, neupravuj bez souhlasu. První iterace = funkční klon BeerBota s jinou personou a KB, ne redesign.

2. **Nevymýšlet fakta o festivalu.** Cokoliv co jde do KB musí pocházet z reálných zdrojů (web festivalu, materiály od klienta). Když něco chybí, flagni to jako otázku pro klienta, nikdy to nedomýšlej.

3. **CORS před produkcí zúžit.** BeerBot má stále `allow_origins=["*"]` — to je dev default. Před nasazením na doménu festivalu zúžit na konkrétní domény.

4. **KB naplnit maximem, ale nikdy nevymýšlet.** KB má pokrývat všechno,
   co lze zodpovědně tvrdit z ověřených zdrojů (oficiální web festivalu,
   materiály od klienta, komiks Boii, dobové prameny). Cíl je, aby bot
   byl od prvního dne viditelně užitečný a klient měl radost, ne aby na
   něj házel polovinu odpovědností. Chybějící informace (např. konkrétní
   program ročníku, ceny merche, telefony penzionů) bot neimprovizuje —
   místo toho elegantně odkáže dál (na lughnasad.cz, na příslušný e-mail,
   na info stánek). Lepší čestné „tohle mi ještě neřekli, ale najdeš to
   zde…" než halucinace.

5. **System prompt je v `config.json`, ne v kódu.** Ať ho klient (a já) může editovat bez redeploy.

6. **Před každou větší změnou: git commit.** Ať se dá vrátit.

7. **Refactor názvů:** repo se jmenuje `askrabbit-lughnasad`, ale uvnitř (v kódu, hlavičkách, meta tazích) může být stále odkaz na "wr-chatbot-template" / "BeerBot". Projít a přepsat na AskRabbit / Diviciacus / Lughnasad.

---

## Kdo jsem já

Martin Svoboda, White Rabbit (Praha). Nejsem programátor — vedl jsem vývojářské studio, rozumím architektuře a produktu, ale kód sám nepíšu. Vibe coder. Piš mi diffy a vysvětlení v češtině, krátce a věcně. Když něco navrhuješ, řekni **proč** a jaké jsou alternativy. Když narazíš na rozhodnutí (knihovna, pattern, pojmenování), zeptej se mě než to uděláš.

Commit messages piš anglicky, krátce, conventional commits formát (`feat:`, `fix:`, `refactor:`, `docs:`).
