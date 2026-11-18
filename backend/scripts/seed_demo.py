"""Seed the database with clearly-labelled DEMO articles so the dashboard works offline.

All outlets and stories here are fictional. Every article is still run through the real NLP engine,
so sentiment / summaries / keywords / bias are computed, not hard-coded.

    python -m scripts.seed_demo            # add demo data
    python -m scripts.seed_demo --clear    # remove demo data
"""
import argparse
import base64
import random
from datetime import timedelta

from app.db import Base, SessionLocal, engine, utcnow
from app.models import Article
from app.nlp.engine import get_engine

# fictional outlets: (name, bias prior, tone tendency: -1 gloomy .. +1 upbeat, sensational 0..1)
OUTLETS = [
    ("Northern Ledger", -0.55, -0.1, 0.4),
    ("Metro Courier", -0.25, 0.1, 0.2),
    ("Global Dispatch", 0.0, 0.0, 0.1),
    ("Heartland Review", 0.35, -0.2, 0.4),
    ("Liberty Standard", 0.7, -0.4, 0.7),
]

# Each event has three framings of the same facts.
EVENTS = [
    ("Economy", "Central bank holds interest rates steady",
     ("The central bank held interest rates steady on Wednesday, saying inflation is easing gradually. Officials noted that hiring remains stable and consumer spending is healthy. Markets reacted calmly to the decision.",
      "Central bank delivers welcome relief as rates stay steady and inflation keeps cooling. Households and businesses welcomed the stability, with strong hiring and a resilient economy giving analysts reasons for optimism.",
      "Central bank refuses to cut rates, leaving struggling families facing painful borrowing costs. Critics slammed the decision as a reckless gamble while mortgage payments and prices stay punishing.")),
    ("Technology", "Chipmaker unveils new AI processor",
     ("A major chipmaker unveiled a new AI processor designed for data centers on Tuesday. The company said the chip will ship next year and improve energy efficiency over its predecessor.",
      "Chipmaker unveils stunning AI processor, a breakthrough that promises faster and cleaner computing. Engineers hailed the design as a major triumph that could help researchers solve problems once thought impossible.",
      "Chipmaker's AI processor raises alarm over soaring energy demand and job losses. Experts warned the powerful new hardware could deepen a dangerous concentration of power among a few giant firms.")),
    ("Climate", "City approves large solar and storage project",
     ("City officials approved a large solar farm with battery storage on Thursday. The project is expected to supply power to about 80,000 homes and begin operating in two years.",
      "City celebrates historic approval of a huge solar farm that will deliver clean, affordable power to thousands of homes. Residents praised the project as a bright step toward a healthier, greener future.",
      "Residents furious as city rushes through massive solar project despite concerns over farmland and rising costs. Opponents called the approval a shameful betrayal of local communities.")),
    ("Health", "Study links daily walking to lower heart risk",
     ("A large study published this week found that adults who walk regularly have a lower risk of heart disease. Researchers followed more than 40,000 participants over eight years.",
      "Great news for public health: a major study shows that simply walking every day can dramatically improve heart health. Doctors called the results encouraging and a simple way to live longer.",
      "Study exposes the grim toll of sedentary life as heart disease remains a deadly threat. Researchers warned that millions are ignoring the danger and the crisis is getting worse.")),
    ("Sports", "National team qualifies for championship final",
     ("The national team qualified for the championship final after a 2-1 win in the semifinal on Saturday. The final will be played next weekend in the capital.",
      "Fans erupt in joy as the national team storms into the championship final with a thrilling comeback victory. The brilliant performance delighted supporters and lifted spirits across the country.",
      "National team scrapes into the final after a sloppy, nervous display that exposed serious defensive flaws. Critics warned the squad will be crushed unless it fixes its disastrous mistakes.")),
    ("Science", "Space agency confirms next lunar mission date",
     ("The space agency confirmed the launch date for its next lunar mission and named the four-person crew. Training will continue through the winter, officials said.",
      "Space agency celebrates a proud milestone as the crew for its historic lunar mission is revealed. Excitement is soaring as the mission promises inspiring discoveries for all humanity.",
      "Space agency's lunar mission faces fresh doubts over delays and ballooning costs. Watchdogs criticized the troubled program as a costly mess that keeps missing its targets.")),
    ("Economy", "Retail sales data released for the quarter",
     ("Retail sales rose 0.4 percent in the quarter, according to official data released on Friday. Online sales grew faster than sales at physical stores.",
      "Retail sales climb again as shoppers show confidence, with online retailers enjoying a strong and profitable quarter. Analysts said the healthy numbers point to a growing economy.",
      "Retail sales barely limp higher while small shops struggle and closures mount. Analysts warned that weak demand and punishing prices threaten a painful slowdown.")),
    ("Technology", "Social platform announces new privacy controls",
     ("A large social platform announced new privacy controls on Monday that let users limit who can see their posts. The features roll out over the coming month.",
      "Social platform delivers welcome privacy upgrade, giving users powerful new tools to protect their personal data. Advocates praised the move as a positive and long overdue improvement.",
      "Social platform's privacy changes are too little, too late, critics say, after years of damaging data scandals. Campaigners blasted the update as a hollow gesture that fails users.")),
    ("Health", "Hospitals report rise in seasonal flu cases",
     ("Hospitals reported a rise in seasonal flu cases this week. Health officials encouraged vaccination and said capacity is currently manageable.",
      "Vaccination drive is working as hospitals say they are coping well with seasonal flu. Officials were encouraged by strong turnout and urged residents to keep protecting each other.",
      "Hospitals brace for a dangerous flu surge as wards fill and staff shortages worsen. Doctors warned of a looming crisis and exhausted teams pushed to breaking point.")),
    ("Climate", "River authority issues flood preparedness guidance",
     ("The river authority issued flood preparedness guidance for riverside districts after forecasts of heavy rain. Sandbags will be distributed at community centers.",
      "Quick action by the river authority impresses residents as communities pull together to prepare for heavy rain. Volunteers were praised for a helpful and well organized response.",
      "Flood fears grow as heavy rain threatens riverside homes and officials are accused of acting too late. Residents said they feel abandoned and terrified of another devastating disaster.")),
]


PALETTES = {
    "Economy": ("#0f766e", "#34d399"), "Technology": ("#3730a3", "#60a5fa"), "Climate": ("#166534", "#2dd4bf"),
    "Health": ("#9d174d", "#fb7185"), "Sports": ("#c2410c", "#fbbf24"), "Science": ("#4c1d95", "#a78bfa"),
}


def demo_art(topic: str, rnd: random.Random) -> str:
    """Generate abstract topic-coloured artwork as an inline SVG data URI (no external images needed offline)."""
    c1, c2 = PALETTES.get(topic, ("#1e293b", "#64748b"))
    shapes = []
    for _ in range(7):
        x, y, r = rnd.randint(0, 640), rnd.randint(0, 360), rnd.randint(40, 170)
        shapes.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" fill-opacity="{rnd.choice([0.05, 0.08, 0.12])}"/>')
    for i in range(5):
        y = 220 + i * 28 + rnd.randint(-8, 8)
        shapes.append(f'<path d="M0 {y} C 160 {y - 50}, 320 {y + 50}, 640 {y - 10} L640 360 L0 360Z" fill="#000" fill-opacity="0.07"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" preserveAspectRatio="xMidYMid slice"><defs>'
           f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
           f'<rect width="640" height="360" fill="url(#g)"/>{"".join(shapes)}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def run(clear: bool = False, seed: int = 7):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.query(Article).filter(Article.is_demo.is_(True)).delete()
        db.commit()
        if clear:
            print("demo data removed")
            return

    rnd = random.Random(seed)
    nlp = get_engine()
    now = utcnow()
    count = 0
    with SessionLocal() as db:
        # 7 days of events; the last 24h is weighted towards Climate/Technology to create visible trends
        for day in range(7):
            for _ in range(rnd.randint(4, 6)):
                recent = day == 0
                pool = [e for e in EVENTS if e[0] in ("Climate", "Technology")] * 2 + EVENTS if recent else EVENTS
                topic, headline, framings = rnd.choice(pool)
                t0 = now - timedelta(days=day, hours=rnd.uniform(0, 22 if day else 10))
                art = demo_art(topic, rnd)  # same artwork for every outlet covering this story
                for name, prior, tone, sensational in rnd.sample(OUTLETS, rnd.randint(3, 5)):
                    r = rnd.random()
                    # pick framing by outlet tone with noise: 0 neutral, 1 upbeat, 2 gloomy
                    up, down = max(0, 0.3 + tone) * 0.6, max(0, 0.3 - tone) * 0.9 + sensational * 0.3
                    k = 1 if r < up else 2 if r < up + down else 0
                    body = framings[k]
                    title = headline if k == 0 else body.split(". ")[0].rstrip(".")
                    a = nlp.analyze(title, body, prior)
                    db.add(
                        Article(
                            url=f"https://demo.invalid/{name.lower().replace(' ', '-')}/{count}",
                            title=title,
                            source=name,
                            content=body,
                            image_url=art,
                            published_at=t0 + timedelta(minutes=rnd.randint(0, 240)),
                            is_demo=True,
                            **a.__dict__,
                        )
                    )
                    count += 1
        db.commit()
    print(f"seeded {count} demo articles using {nlp.description}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true")
    run(ap.parse_args().clear)
