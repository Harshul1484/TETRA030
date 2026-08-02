import { api, type GraphData } from "@/lib/api";
import { SkillGraph } from "@/components/skill-graph";
import { CATEGORY_BLOCKS } from "@/lib/theme";
import { Card, ErrorPanel, SectionTitle, Stat } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function GraphPage() {
  let data: GraphData | null = null;
  let error: string | null = null;

  try {
    data = await api.graph(70);
  } catch (exception) {
    error = exception instanceof Error ? exception.message : String(exception);
  }

  if (error || !data) return <ErrorPanel message={error ?? "No graph data"} />;

  return (
    <div className="space-y-12">
      <section>
        <h1 className="display-lg text-[var(--color-ink)]">
          Skill Ontology Graph
        </h1>
        <p className="mt-4 max-w-3xl text-[16px] leading-relaxed text-[var(--color-ink-soft)]">
          Skills ranked by market demand, joined by prerequisite edges. Node
          colour is the skill category, matching the tags used throughout the
          gap reports. A dark ring marks a skill the curriculum already
          teaches; everything unringed is a gap. Node size is how many
          postings ask for the skill.
        </p>
      </section>

      <div className="grid gap-6 border-y border-[var(--color-hairline)] py-8 sm:grid-cols-4">
        <Stat label="Skills shown" value={data.summary.skills} />
        <Stat label="Taught" value={data.summary.taught} />
        <Stat label="Gaps" value={data.summary.gaps} />
        <Stat label="Prerequisite edges" value={data.summary.edges} />
      </div>

      <SkillGraph data={data} />

      <div className="flex flex-wrap gap-2.5">
        {Object.entries(CATEGORY_BLOCKS)
          .filter(([key]) => data.nodes.some((node) => node.category === key))
          .map(([key, block]) => (
            <span
              key={key}
              className="micro-cap inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] px-2.5 py-1.5"
              style={{ backgroundColor: block.bg }}
            >
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: block.dot }}
              />
              {block.label}
            </span>
          ))}
      </div>

      <Card block="var(--color-block-sky)">
        <SectionTitle>Why this is a graph, not a table</SectionTitle>
        <p className="text-[15px] leading-relaxed text-[var(--color-ink-soft)]">
          The edges are what make the analysis actionable. Knowing a curriculum
          is missing Retrieval Augmented Generation is only useful alongside
          what it would cost to teach: the graph resolves that to Large Language
          Models and Vector Databases at one hop, Embeddings and Transformers at
          two, and Deep Learning at three. Answering that in a relational schema
          needs a recursive query that degrades with every additional hop.
        </p>
      </Card>
    </div>
  );
}
