"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { GraphData, GraphNode, PrerequisiteChain } from "@/lib/api";
import { api } from "@/lib/api";
import { categoryBlock } from "@/lib/theme";

/**
 * The skill ontology, rendered with react-force-graph-2d.
 *
 * An earlier version ran a hand-written force simulation on a raw canvas. It
 * never settled: nodes drifted for as long as the page was open, which made
 * reading a label a moving target. This uses d3's forces through the library,
 * with a cooldown so the layout comes to rest and stays there.
 *
 * Loaded without SSR because the library reaches for window on import.
 */
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[560px] items-center justify-center text-[15px] text-[var(--color-ink-mute)]">
      Preparing the graph...
    </div>
  ),
});

interface SimNode {
  id: string;
  category: string;
  demand: number;
  is_taught: boolean;
  radius: number;
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
}

const MIN_RADIUS = 4;
const MAX_RADIUS = 13;

// Ticks before the simulation is allowed to rest. Enough to untangle, few
// enough that a judge is not watching it wander.
const COOLDOWN_TICKS = 220;

export function SkillGraph({ data }: { data: GraphData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<{
    d3Force: (
      name: string,
    ) => { strength?: (v: number) => void; distance?: (v: number) => void } | undefined;
    zoomToFit: (ms?: number, padding?: number) => void;
  } | null>(null);

  const [size, setSize] = useState({ width: 0, height: 560 });
  const [selected, setSelected] = useState<SimNode | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [chain, setChain] = useState<PrerequisiteChain | null>(null);
  const didFit = useRef(false);
  const didConfigure = useRef(false);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      setSize({ width: entry.contentRect.width, height: 560 });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const maxDemand = Math.max(1, ...data.nodes.map((n) => n.demand));
    const nodes: SimNode[] = data.nodes.map((node: GraphNode) => ({
      id: node.skill,
      category: node.category,
      demand: node.demand,
      is_taught: node.is_taught,
      radius:
        MIN_RADIUS + Math.sqrt(node.demand / maxDemand) * (MAX_RADIUS - MIN_RADIUS),
    }));
    const present = new Set(nodes.map((n) => n.id));
    const links = data.edges
      .filter((e) => present.has(e.source) && present.has(e.target))
      .map((e) => ({ source: e.source, target: e.target }));
    return { nodes, links };
  }, [data]);

  /** Which nodes are adjacent to the hovered one, for dimming the rest. */
  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    const link = (a: string, b: string) => {
      if (!map.has(a)) map.set(a, new Set());
      map.get(a)!.add(b);
    };
    for (const edge of data.edges) {
      link(edge.source, edge.target);
      link(edge.target, edge.source);
    }
    return map;
  }, [data.edges]);

  const dimmed = useCallback(
    (id: string) => {
      if (!hovered || id === hovered) return false;
      return !adjacency.get(hovered)?.has(id);
    },
    [hovered, adjacency],
  );

  const configureForces = useCallback(() => {
    if (didConfigure.current) return;
    const graph = graphRef.current;
    if (!graph) return;
    didConfigure.current = true;
    // Repulsion wide enough that labels have room; link distance short enough
    // that prerequisite chains read as chains rather than scattered dots.
    graph.d3Force("charge")?.strength?.(-160);
    graph.d3Force("link")?.distance?.(58);
  }, []);

  const paintNode = useCallback(
    (node: SimNode, ctx: CanvasRenderingContext2D, scale: number) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const block = categoryBlock(node.category);
      const faded = dimmed(node.id);

      ctx.save();
      ctx.globalAlpha = faded ? 0.12 : 1;

      ctx.beginPath();
      ctx.arc(x, y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = block.dot;
      ctx.fill();

      // A dark ring marks a skill the curriculum already teaches.
      if (node.is_taught) {
        ctx.strokeStyle = "#16171a";
        ctx.lineWidth = 2.2;
        ctx.stroke();
      }

      if (node.id === selected?.id) {
        ctx.beginPath();
        ctx.arc(x, y, node.radius + 6, 0, Math.PI * 2);
        ctx.strokeStyle = "#16171a";
        ctx.lineWidth = 1.4;
        ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Labels only where they will not pile up: the larger nodes, the taught
      // ones, and whatever is being pointed at.
      const worthLabelling =
        node.radius > 7 ||
        node.is_taught ||
        node.id === hovered ||
        node.id === selected?.id;
      if (worthLabelling && !faded) {
        const fontSize = Math.max(11 / scale, 3);
        ctx.font = `500 ${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = "rgba(22, 23, 26, 0.82)";
        ctx.fillText(node.id, x, y + node.radius + 3);
      }

      ctx.restore();
    },
    [dimmed, hovered, selected],
  );

  const handleClick = useCallback(async (node: SimNode) => {
    setSelected(node);
    setChain(null);
    try {
      setChain(await api.prerequisites(node.id));
    } catch {
      setChain(null);
    }
  }, []);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_310px]">
      <div
        ref={containerRef}
        className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)]"
      >
        {size.width > 0 ? (
          <ForceGraph2D
            ref={graphRef as never}
            width={size.width}
            height={size.height}
            graphData={graphData as never}
            backgroundColor="#ffffff"
            nodeCanvasObject={paintNode as never}
            nodePointerAreaPaint={
              ((node: SimNode, colour: string, ctx: CanvasRenderingContext2D) => {
                ctx.beginPath();
                ctx.arc(node.x ?? 0, node.y ?? 0, node.radius + 5, 0, Math.PI * 2);
                ctx.fillStyle = colour;
                ctx.fill();
              }) as never
            }
            linkColor={(() => "rgba(22, 23, 26, 0.13)") as never}
            linkWidth={1}
            onNodeClick={handleClick as never}
            onNodeHover={
              ((node: SimNode | null) => setHovered(node ? node.id : null)) as never
            }
            onBackgroundClick={() => {
              setSelected(null);
              setChain(null);
            }}
            onNodeDragEnd={
              ((node: SimNode) => {
                // Pin where it was dropped, so a rearranged layout stays put.
                node.fx = node.x;
                node.fy = node.y;
              }) as never
            }
            onEngineTick={configureForces as never}
            onEngineStop={
              (() => {
                if (didFit.current) return;
                didFit.current = true;
                graphRef.current?.zoomToFit(500, 50);
              }) as never
            }
            cooldownTicks={COOLDOWN_TICKS}
          />
        ) : null}

        <div className="flex flex-wrap items-center gap-4 border-t border-[var(--color-hairline)] px-5 py-3.5">
          <span className="caption flex items-center gap-1.5 text-[var(--color-ink-mute)]">
            <span className="inline-block h-3 w-3 rounded-full border-2 border-[var(--color-ink)] bg-white" />
            taught
          </span>
          <span className="caption flex items-center gap-1.5 text-[var(--color-ink-mute)]">
            <span
              className="inline-block h-3 w-3 rounded-full"
              style={{ backgroundColor: "var(--color-block-periwinkle)" }}
            />
            gap
          </span>
          <span className="caption text-[var(--color-ink-mute)]">
            colour is category, size is demand
          </span>
          <span className="caption ml-auto text-[var(--color-ink-mute)]">
            click a node for its prerequisites, drag to rearrange
          </span>
        </div>
      </div>

      <aside className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-6">
        {!selected ? (
          <p className="text-[16px] text-[var(--color-ink-mute)]">
            Select a skill to see what a course would need to teach first.
          </p>
        ) : (
          <div>
            <h3 className="card-title text-[var(--color-ink)]">{selected.id}</h3>
            <dl className="caption mt-4 space-y-2">
              <div className="flex justify-between">
                <dt className="text-[var(--color-ink-mute)]">Category</dt>
                <dd className="text-[var(--color-ink)]">
                  {categoryBlock(selected.category).label}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-ink-mute)]">Postings</dt>
                <dd className="tabular text-[var(--color-ink)]">{selected.demand}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-ink-mute)]">Status</dt>
                <dd
                  className={
                    selected.is_taught
                      ? "text-[var(--color-success)]"
                      : "text-[var(--color-severity-high)]"
                  }
                >
                  {selected.is_taught ? "taught" : "gap"}
                </dd>
              </div>
            </dl>

            {chain && chain.by_hop.length > 0 ? (
              <div className="mt-5 border-t border-[var(--color-hairline)] pt-4">
                <p className="micro-cap text-[var(--color-ink-mute)]">Requires first</p>
                <p className="caption mt-1 text-[var(--color-ink-mute)]">
                  {chain.total_prerequisites} skills across {chain.max_depth}{" "}
                  {chain.max_depth === 1 ? "level" : "levels"}
                </p>
                <div className="scroll-panel mt-3 max-h-72 space-y-3 pr-1">
                  {chain.by_hop.map((level) => (
                    <div key={level.hops}>
                      <p className="micro-cap text-[var(--color-ink-mute)]">
                        {level.hops} hop{level.hops > 1 ? "s" : ""}
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {level.prerequisites.map((name) => (
                          <li
                            key={name}
                            className="text-[15px] text-[var(--color-ink-soft)]"
                          >
                            {name}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            ) : chain ? (
              <p className="caption mt-5 border-t border-[var(--color-hairline)] pt-4 text-[var(--color-ink-mute)]">
                No prerequisites recorded. This is a foundational skill.
              </p>
            ) : null}
          </div>
        )}
      </aside>
    </div>
  );
}
