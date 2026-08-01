import { api, type GraphData } from "@/lib/api";
import { SkillGraph } from "@/components/skill-graph";
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
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">
          Skill Ontology Graph
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
          Skills ranked by market demand, joined by prerequisite edges. Green
          nodes are taught by the curriculum; amber nodes are demanded by
          employers but not covered. Node size reflects how many postings ask
          for the skill.
        </p>
      </section>

      <div className="grid gap-4 sm:grid-cols-4">
        <Card>
          <Stat label="Skills shown" value={data.summary.skills} />
        </Card>
        <Card>
          <Stat label="Taught" value={data.summary.taught} />
        </Card>
        <Card>
          <Stat label="Gaps" value={data.summary.gaps} />
        </Card>
        <Card>
          <Stat label="Prerequisite edges" value={data.summary.edges} />
        </Card>
      </div>

      <SkillGraph data={data} />

      <Card className="bg-slate-900/20">
        <SectionTitle>Why this is a graph, not a table</SectionTitle>
        <p className="text-sm leading-relaxed text-slate-400">
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
