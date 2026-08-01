import { Card, SectionTitle } from "@/components/ui";

const STAGES = [
  {
    name: "Ingest",
    detail:
      "Syllabi are parsed from PDF or DOCX. Job postings come from a committed snapshot of real listings, so results are reproducible and work offline.",
  },
  {
    name: "Extract",
    detail:
      "Claude reads each document and identifies skills, constrained to a curated taxonomy. It cannot invent a skill the ontology does not know.",
  },
  {
    name: "Embed",
    detail:
      "All 438 canonical skills are embedded locally with sentence-transformers into ChromaDB. No paid embedding API is involved.",
  },
  {
    name: "Match",
    detail:
      "Mentions resolve to canonical skills. Exact alias resolution runs first because it is certain; vector similarity handles paraphrases the taxonomy cannot enumerate.",
  },
  {
    name: "Score",
    detail:
      "A Cypher traversal compares taught skills against demanded ones and measures the prerequisite distance between them. Four signals combine into the health score.",
  },
  {
    name: "Augment",
    detail:
      "Claude proposes additions that extend existing units, using the gap report and the course subgraph as context.",
  },
];

export default function AboutPage() {
  return (
    <div className="space-y-14">
      <section>
        <h1 className="display-lg text-[var(--color-ink)]">
          How It Works
        </h1>
        <p className="body-lg mt-5 max-w-3xl text-[var(--color-ink-soft)]">
          Higher education curricula lag three to five years behind market
          demand, and institutions have no automated way to measure the drift.
          CurricuAlign maps course outcomes and live job postings onto one skill
          ontology, then quantifies the distance between them.
        </p>
      </section>

      <Card>
        <SectionTitle hint="Each stage has one responsibility and a stable interface, so any of them can be replaced without touching its neighbours.">
          The pipeline
        </SectionTitle>
        <ol className="space-y-3">
          {STAGES.map((stage, index) => (
            <li key={stage.name} className="flex gap-4">
              <span className="tabular mt-0.5 text-[13px] text-[var(--color-ink-mute)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="card-title text-[var(--color-ink)]">
                  {stage.name}
                </p>
                <p className="mt-1.5 text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
                  {stage.detail}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <Card block="var(--color-block-periwinkle)">
        <SectionTitle>What makes this different</SectionTitle>
        <p className="text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
          Most curriculum tools compare word lists and report what is missing.
          This one records which skills are prerequisites for which, so it can
          answer a harder question: what would it cost to close the gap?
        </p>
        <p className="mt-3 text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
          Adding Kubernetes to a course that already teaches Docker is one hop
          and cheap. Adding Retrieval Augmented Generation to a course covering
          none of Vector Databases, Large Language Models, Embeddings, or Deep
          Learning is a four-hop chain and a different conversation entirely. A
          keyword diff produces a complaint; a graph produces a sequencing plan.
        </p>
      </Card>

      <Card block="var(--color-block-orchid)">
        <SectionTitle>Honest limitations</SectionTitle>
        <ul className="space-y-2.5 text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
          <li>
            Embeddings do not encode negation. The phrase &quot;finding patterns
            without labelled examples&quot; retrieves Supervised Learning rather
            than its opposite, which is why exact taxonomy resolution runs first
            and vector hits never override a certain match.
          </li>
          <li>
            The job corpus spans roughly one month. Free job APIs serve current
            listings only, so month-granularity trends are supported but a
            multi-year demand forecast is not.
          </li>
          <li>
            Gap scoring weights are a first estimate, tuned by judgment rather
            than measurement. The similarity threshold, by contrast, was
            calibrated against measured data and is reproducible from a
            committed script.
          </li>
          <li>
            Scanned PDFs without a text layer are rejected rather than run
            through OCR.
          </li>
        </ul>
      </Card>

      <Card block="var(--color-block-butter)">
        <SectionTitle>Stack</SectionTitle>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {[
            ["Skill ontology", "Neo4j, 438 skills and 587 prerequisite edges"],
            ["Semantic search", "ChromaDB with local sentence-transformers"],
            ["Extraction and generation", "Claude, every call cached by content hash"],
            ["Backend", "FastAPI and Python"],
            ["Frontend", "Next.js with types generated from the OpenAPI schema"],
            ["Job market data", "Arbeitnow and Remotive"],
          ].map(([term, detail]) => (
            <div key={term}>
              <dt className="micro-cap text-[var(--color-ink-mute)]">
                {term}
              </dt>
              <dd className="mt-1 text-[var(--color-ink)]">{detail}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}
