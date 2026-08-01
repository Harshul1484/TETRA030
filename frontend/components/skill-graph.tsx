"use client";

import { useEffect, useRef, useState } from "react";

import type { GraphData, GraphNode, PrerequisiteChain } from "@/lib/api";
import { api } from "@/lib/api";
import { categoryBlock } from "@/lib/theme";

/**
 * Force-directed layout on a canvas.
 *
 * The simulation is written directly rather than pulled from a library: it is
 * about sixty lines, and a graph rendering dependency is a large amount of
 * surface area for one screen.
 */

interface Body extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

const REPULSION = 9000;
const SPRING = 0.02;
const SPRING_LENGTH = 78;
const CENTERING = 0.006;
const DAMPING = 0.82;
const MIN_RADIUS = 4;
const MAX_RADIUS = 15;

// Nodes were piling up along the canvas edges because the position clamp
// pinned them there without removing the velocity that pushed them out.
// Keeping a margin and reflecting velocity on contact keeps the layout inside
// the frame without creating a wall of stuck nodes.
const MARGIN = 60;
const WALL_BOUNCE = -0.4;

export function SkillGraph({ data }: { data: GraphData }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [chain, setChain] = useState<PrerequisiteChain | null>(null);
  const bodiesRef = useRef<Body[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const maxDemand = Math.max(1, ...data.nodes.map((node) => node.demand));

    const bodies: Body[] = data.nodes.map((node, index) => {
      const angle = (index / data.nodes.length) * Math.PI * 2;
      const spread = 150 + (index % 5) * 40;
      return {
        ...node,
        x: canvas.width / 2 + Math.cos(angle) * spread,
        y: canvas.height / 2 + Math.sin(angle) * spread,
        vx: 0,
        vy: 0,
        radius:
          MIN_RADIUS +
          (Math.sqrt(node.demand / maxDemand) || 0) * (MAX_RADIUS - MIN_RADIUS),
      };
    });
    bodiesRef.current = bodies;

    const byName = new Map(bodies.map((body) => [body.skill, body]));
    const links = data.edges
      .map((edge) => ({
        a: byName.get(edge.source),
        b: byName.get(edge.target),
      }))
      .filter((link): link is { a: Body; b: Body } => !!link.a && !!link.b);

    let frame = 0;
    let raf = 0;

    function step() {
      for (let i = 0; i < bodies.length; i++) {
        for (let j = i + 1; j < bodies.length; j++) {
          const a = bodies[i];
          const b = bodies[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const distanceSquared = dx * dx + dy * dy || 1;
          const distance = Math.sqrt(distanceSquared);
          const force = REPULSION / distanceSquared;
          const fx = (dx / distance) * force;
          const fy = (dy / distance) * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }
      }

      for (const link of links) {
        const dx = link.b.x - link.a.x;
        const dy = link.b.y - link.a.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (distance - SPRING_LENGTH) * SPRING;
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        link.a.vx += fx;
        link.a.vy += fy;
        link.b.vx -= fx;
        link.b.vy -= fy;
      }

      const cx = canvas!.width / 2;
      const cy = canvas!.height / 2;

      const minX = MARGIN;
      const maxX = canvas!.width - MARGIN;
      const minY = MARGIN * 0.5;
      const maxY = canvas!.height - MARGIN * 0.5;

      for (const body of bodies) {
        body.vx += (cx - body.x) * CENTERING;
        body.vy += (cy - body.y) * CENTERING;
        body.vx *= DAMPING;
        body.vy *= DAMPING;
        body.x += body.vx;
        body.y += body.vy;

        if (body.x < minX) {
          body.x = minX;
          body.vx *= WALL_BOUNCE;
        } else if (body.x > maxX) {
          body.x = maxX;
          body.vx *= WALL_BOUNCE;
        }
        if (body.y < minY) {
          body.y = minY;
          body.vy *= WALL_BOUNCE;
        } else if (body.y > maxY) {
          body.y = maxY;
          body.vy *= WALL_BOUNCE;
        }
      }
    }

    function draw() {
      const ctx = context!;
      ctx.clearRect(0, 0, canvas!.width, canvas!.height);

      ctx.strokeStyle = "rgba(0, 0, 0, 0.13)";
      ctx.lineWidth = 1;
      for (const link of links) {
        ctx.beginPath();
        ctx.moveTo(link.a.x, link.a.y);
        ctx.lineTo(link.b.x, link.b.y);
        ctx.stroke();
      }

      for (const body of bodies) {
        const isSelected = selected?.skill === body.skill;
        ctx.beginPath();
        ctx.arc(body.x, body.y, body.radius, 0, Math.PI * 2);
        // Fill is the category colour so a node matches its gap card and
        // tag; a taught skill gets a solid ink ring to separate it from a gap.
        ctx.fillStyle = categoryBlock(body.category).dot;
        ctx.fill();

        if (body.is_taught) {
          ctx.strokeStyle = "rgba(0, 0, 0, 0.85)";
          ctx.lineWidth = 2.5;
          ctx.stroke();
        }

        if (isSelected) {
          ctx.strokeStyle = "#ff3d8b";
          ctx.lineWidth = 3;
          ctx.stroke();
        }
      }

      // Labels are drawn in a second pass, largest node first, and only where
      // they do not collide with one already placed. Drawing every label
      // produced an unreadable pile in the dense regions.
      ctx.font = "500 11px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";

      const placed: { x1: number; y1: number; x2: number; y2: number }[] = [];
      const ordered = [...bodies].sort((a, b) => {
        if (selected?.skill === a.skill) return -1;
        if (selected?.skill === b.skill) return 1;
        return b.radius - a.radius;
      });

      for (const body of ordered) {
        const isSelected = selected?.skill === body.skill;
        if (!isSelected && !body.is_taught && body.radius < 7) continue;

        const width = ctx.measureText(body.skill).width;
        const x = body.x;
        const y = body.y - body.radius - 6;
        const box = {
          x1: x - width / 2 - 2,
          y1: y - 11,
          x2: x + width / 2 + 2,
          y2: y + 3,
        };

        const collides = placed.some(
          (other) =>
            box.x1 < other.x2 &&
            box.x2 > other.x1 &&
            box.y1 < other.y2 &&
            box.y2 > other.y1,
        );
        if (collides && !isSelected) continue;

        placed.push(box);
        ctx.fillStyle = isSelected ? "#000000" : "rgba(0, 0, 0, 0.72)";
        ctx.fillText(body.skill, x, y);
      }
    }

    function loop() {
      // The layout settles quickly. Running the simulation forever would burn
      // CPU on a page a judge may leave open.
      if (frame < 320) {
        step();
        frame += 1;
      }
      draw();
      raf = requestAnimationFrame(loop);
    }

    loop();
    return () => cancelAnimationFrame(raf);
  }, [data, selected]);

  async function handleClick(event: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((event.clientY - rect.top) / rect.height) * canvas.height;

    const hit = bodiesRef.current.find(
      (body) => Math.hypot(body.x - x, body.y - y) <= body.radius + 6,
    );

    setSelected(hit ?? null);
    setChain(null);

    if (hit) {
      try {
        setChain(await api.prerequisites(hit.skill));
      } catch {
        setChain(null);
      }
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)]">
        <canvas
          ref={canvasRef}
          width={900}
          height={560}
          onClick={handleClick}
          className="h-auto w-full cursor-pointer"
        />
        <div className="flex flex-wrap items-center gap-4 border-t border-[var(--color-hairline)] px-5 py-3.5 caption text-[var(--color-ink-mute)]">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full border-2 border-black bg-[var(--color-surface)]" />
            taught
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: "var(--color-block-periwinkle)" }} />
            gap
          </span>
          <span>node size is market demand</span>
          <span className="ml-auto">click a node for its prerequisites</span>
        </div>
      </div>

      <aside className="rounded-[var(--radius-lg)] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-6">
        {!selected ? (
          <p className="text-[16px] text-[var(--color-ink-mute)]">
            Select a skill to see what a course would need to teach first.
          </p>
        ) : (
          <div>
            <h3 className="card-title text-[var(--color-ink)]">
              {selected.skill}
            </h3>
            <dl className="mt-4 space-y-2 caption">
              <div className="flex justify-between">
                <dt className="text-[var(--color-ink-mute)]">Category</dt>
                <dd className="text-[var(--color-ink)]">{selected.category}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-ink-mute)]">Postings</dt>
                <dd className="tabular text-[var(--color-ink)]">{selected.demand}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-ink-mute)]">Status</dt>
                <dd
                  className={
                    selected.is_taught ? "text-[var(--color-success)]" : "text-[var(--color-severity-high)]"
                  }
                >
                  {selected.is_taught ? "taught" : "gap"}
                </dd>
              </div>
            </dl>

            {chain && chain.by_hop.length > 0 ? (
              <div className="mt-5 border-t border-[var(--color-hairline)] pt-4">
                <p className="micro-cap text-[var(--color-ink-mute)]">
                  Requires first
                </p>
                <p className="caption mt-1 text-[var(--color-ink-mute)]">
                  {chain.total_prerequisites} skills across {chain.max_depth}{" "}
                  levels
                </p>
                <div className="scroll-panel mt-2 max-h-64 space-y-2 pr-1">
                  {chain.by_hop.map((level) => (
                    <div key={level.hops}>
                      <p className="micro-cap text-[var(--color-ink-mute)]">
                        {level.hops} hop{level.hops > 1 ? "s" : ""}
                      </p>
                      <ul className="mt-0.5 space-y-0.5">
                        {level.prerequisites.map((name) => (
                          <li key={name} className="text-[15px] text-[var(--color-ink-soft)]">
                            {name}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            ) : chain ? (
              <p className="mt-5 border-t border-[var(--color-hairline)] pt-4 caption text-[var(--color-ink-mute)]">
                No prerequisites recorded. This is a foundational skill.
              </p>
            ) : null}
          </div>
        )}
      </aside>
    </div>
  );
}
