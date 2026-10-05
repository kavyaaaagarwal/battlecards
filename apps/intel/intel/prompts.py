"""All prompts in one place so the PMM thinking is easy to read and tune."""

CITATION_RULES = """\
CITATION RULES (strict):
- Every claim must list the source IDs (e.g. "S4") that directly support it.
- Use ONLY the sources provided. Never use outside knowledge or guess.
- If the sources don't support something, leave it out. An empty list beats a guess.
- Prices, numbers and dates must appear in a cited source exactly as written.
- Quotes must be copied VERBATIM, character for character, from the source text,
  10-40 words, from real users (reviews, forums) - never marketing copy.

SOURCE ORIGIN: every source is labelled INDEPENDENT or "BY <Company>" (that company's own
site or press release). A company's own pages are fine for what it SAYS it offers, but never
evidence about a rival. Claims about strengths, weaknesses and customer experience should
rest on INDEPENDENT sources (reviews, forums, news, analysts) whenever they exist."""

ANALYST_SYSTEM = f"""\
You are a senior product marketing analyst building competitive intelligence for
a B2B sales team. You are precise, skeptical of marketing claims, and you separate
what a company SAYS (its site) from what customers EXPERIENCE (reviews, forums).
Be concrete: prefer "SSO only on Enterprise tier ($X)" over "strong security".

{CITATION_RULES}"""


def profile_prompt(company: str, domain: str | None, category: str, sources_block: str) -> str:
    return f"""\
Build a factual profile of **{company}**{f" ({domain})" if domain else ""}{f", a {category} vendor" if category else ""}.

Fill each field from the sources below:
- positioning: their own one-line positioning, from their site.
- target_customers: segments/sizes/industries they target.
- key_capabilities: 4-8 capabilities that matter to buyers (not a feature dump).
- pricing_summary + pricing_tiers: tier names and prices exactly as published. If pricing
  is not public, say so in pricing_summary and leave tiers empty.
- recent_changes: launches, pricing changes, acquisitions, notable updates (include dates when stated).
- review_strengths / review_weaknesses: recurring themes from REVIEWS and FORUMS only.
- hiring_signals: what open roles suggest about strategy (only if sources show it).
- ratings: star ratings from review sites (G2, Capterra, TrustRadius, ...) exactly as shown,
  with review counts when stated. One entry per site. Only from INDEPENDENT review-site sources.
- quotes: up to 6 verbatim customer quotes (praise, pain, or reasons for switching), only from
  INDEPENDENT sources (reviews, forums) - never testimonials on a vendor's own site.

Sources about other companies may appear; only use what is about {company}.

SOURCES:
{sources_block}"""


def battlecard_prompt(
    company: str, competitor: str, our_profile: str, their_profile: str, comparison_block: str,
    origins: str = "",
) -> str:
    return f"""\
Write a sales battlecard for **{company}** reps competing against **{competitor}**.
"We" = {company}. Use the two profiles (their claims carry source IDs - reuse those IDs)
and the head-to-head comparison sources.

A rep reads this 2 minutes before a call, or during one. It must be scannable on ONE screen.
Write like a sales leader talking to a rep: short, plain words, no marketing fluff.
HARD LENGTH LIMITS - shorter is better; never exceed them:
- overview: one sentence, max 20 words: who {competitor} is and who they sell to.
- tldr: two short sentences, max 35 words total. "We win when ... We lose when ..."
- quick_dismiss: max 50 words, something a rep can SAY out loud: acknowledge one real
  {competitor} strength, name its limit for the prospect, pivot to our value.
- where_we_win: exactly 3 (fewer if evidence is thin). headline max 10 words (the takeaway,
  e.g. "Native POS integrations for restaurants"); detail = ONE sentence, max 25 words, with the proof.
- where_we_lose: 2-3 honest {competitor} strengths. Same headline/detail limits, plus counter:
  max 20 words on how a rep reframes or neutralises it.
- landmines: 3 questions, max 20 words each, that make the prospect probe a documented
  {competitor} weakness; why = max 15 words naming the weakness it exposes.
- objections: 3. objection = what the prospect says, max 15 words; response = what the rep
  says back, max 35 words, conversational.
- pricing_comparison: an OBJECT {{"text": one sentence max 30 words, "sources": [...]}},
  or say pricing isn't comparable.
- proof_quotes: up to 2 verbatim quotes (copied from the profiles' quotes, keep their source IDs)
  that support our position. Prefer quotes from reviews over vendor pages.
- sources: cite the 1-2 strongest source IDs per item, not every possible one. Prefer
  INDEPENDENT sources. {competitor}'s weaknesses (landmines, counters) must NOT rest on
  {company}'s own pages - our marketing is not proof about them.

Do not invent advantages. Don't cram "we do X, whereas {competitor} does Y" into
one bullet - make the point, then prove it. If the evidence is thin, give fewer, stronger points.

OUR PROFILE ({company}):
{our_profile}

THEIR PROFILE ({competitor}):
{their_profile}

HEAD-TO-HEAD SOURCES (independent comparisons):
{comparison_block}

WHO PUBLISHED EACH SOURCE ID USED IN THE PROFILES:
{origins}"""


def positioning_prompt(company: str, profiles_block: str) -> str:
    return f"""\
Analyse the positioning landscape for **{company}** and its competitors.

- table_stakes: themes that most players claim (these do NOT differentiate). List which
  companies claim each.
- white_space: buyer needs or pains that show up in reviews/forums but that no company
  clearly owns in its positioning. Cite the evidence.
- recommended_angle: one positioning angle {company} could credibly own, grounded in
  its documented strengths and the white space. One or two sentences, cited.

PROFILES (claims carry source IDs - reuse them):
{profiles_block}"""


def diff_prompt(company: str, previous_block: str, current_block: str) -> str:
    return f"""\
Compare last run's competitive profiles with this run's, for {company}'s PMM team.

List only MEANINGFUL changes: pricing or packaging changes, new launches, new target
segments, messaging shifts, new recurring complaints, notable hiring shifts.
Ignore wording differences and things that were merely found/not found this time
due to search variance (only report a change if the CURRENT run positively shows it).

For each: what changed, why it matters to {company}'s sales/marketing, severity
(high = affects deals this quarter), and source IDs from the CURRENT run.
Return an empty list if nothing meaningful changed.

PREVIOUS RUN:
{previous_block}

CURRENT RUN:
{current_block}"""


def matrix_prompt(company: str, companies: list[str], category: str, profiles_block: str,
                  sources_block: str, origins: str) -> str:
    names = ", ".join(companies)
    return f"""\
Build a capability comparison matrix for a {category or "B2B software"} buying decision:
{names}. "{company}" is the company the sales team sells.

- capabilities: 6-8 capabilities BUYERS in this category actually compare (from the review
  sites, independent round-ups and profiles) - not marketing slogans. Name each in max 5 words.
  Include ones where {company} is weak, not only where it is strong.
- For EVERY capability give one cell per company ({names}), with status:
    full    = clearly offered as part of the product
    partial = limited, add-on/extra cost, or reviewers report it is weak
    none    = a source explicitly says it is not offered
    unknown = the sources don't say (this is the honest default)
  note: max 8 words (e.g. "Add-on, extra cost", "Native, no partner needed").
  sources: the IDs supporting that cell. A company's own site may support its OWN cells;
  it is never evidence for another company's cell.

PROFILES (claims carry source IDs - reuse them):
{profiles_block}

INDEPENDENT COMPARISONS AND ROUND-UPS:
{sources_block}

WHO PUBLISHED EACH SOURCE ID:
{origins}"""
