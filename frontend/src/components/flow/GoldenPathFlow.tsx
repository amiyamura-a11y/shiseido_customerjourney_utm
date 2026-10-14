"use client";
import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState, forwardRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  useReactFlow,
  getNodesBounds,
  getViewportForBounds,
  ReactFlowProvider,
  type Node,
  type Edge,
  type NodeProps,
  type EdgeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toPng, toSvg } from "html-to-image";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";
import { colorFor } from "./palette";
import { num, pct, days } from "@/lib/format";

export interface GoldenPathFlowHandle {
  exportPng: (filename: string) => Promise<void>;
  exportSvg: (filename: string) => Promise<void>;
  fit: () => void;
}

interface Props {
  graph: GraphResponse;
  selectedNodes: { step: number; label: string }[];
  selectedEdges: { step: number; source: string; target: string }[];
  onNodeClick?: (step: number, label: string) => void;
  onEdgeClick?: (step: number, source: string, target: string) => void;
  highlightPath?: string[] | null;
  height?: number;
  scale?: { maxRate: number; maxCount: number } | null;
  nodeOrder?: Record<string, string[]> | null;
  compact?: boolean;
}

const COL_W = 200;
const D_MIN = 46;
const D_MAX = 118;
const HEADER_H = 46;
const GAP = 14;

type GpNodeData = { gn: GraphNode; d: number; selected: boolean; dimmed: boolean; onClick?: () => void; onHover?: (gn: GraphNode | null, e?: React.MouseEvent) => void };
type GpEdgeData = { ge: GraphEdge; width: number; dimmed: boolean; selected: boolean; showLabel: boolean; onClick?: () => void };

function GpNode({ data }: NodeProps<Node<GpNodeData>>) {
  const { gn, d, selected, dimmed } = data;
  const isOutcome = gn.kind === "outcome";
  const bg = colorFor(gn.label);
  const style: React.CSSProperties = isOutcome
    ? { width: 132, height: 58, borderRadius: 10, background: bg }
    : { width: d, height: d, background: bg };
  return (
    <div
      className={`gp-node ${selected ? "selected" : ""} ${dimmed ? "dimmed" : ""}`}
      style={style}
      onClick={data.onClick}
      onMouseEnter={(e) => data.onHover?.(gn, e)}
      onMouseMove={(e) => data.onHover?.(gn, e)}
      onMouseLeave={() => data.onHover?.(null)}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0, pointerEvents: "none" }} />
      <div className="lbl" style={{ fontSize: d < 60 && !isOutcome ? 9 : 10.5 }}>{isOutcome ? gn.label : gn.label.replace(/ \d+回目$/, "")}</div>
      <div className="pct">{isOutcome ? `${num(gn.count)}人` : `${(gn.label.match(/ (\d+回目)$/)?.[1] ?? "") ? `${gn.label.match(/ (\d+回目)$/)![1]} · ` : ""}${pct(gn.rate, 0)}`}</div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0, pointerEvents: "none" }} />
    </div>
  );
}

function GpEdge({ id, sourceX, sourceY, targetX, targetY, data, markerEnd }: EdgeProps<Edge<GpEdgeData>>) {
  const [path, lx, ly] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition: Position.Right, targetPosition: Position.Left, curvature: 0.35 });
  const d = data!;
  const stroke = d.selected ? "#101016" : "#8a8a98";
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={{ strokeWidth: d.width, stroke, opacity: d.dimmed ? 0.12 : d.selected ? 0.95 : 0.55 }} />
      <path d={path} fill="none" stroke="transparent" strokeWidth={Math.max(14, d.width + 10)} style={{ cursor: "pointer", pointerEvents: "stroke" }} onClick={d.onClick} />
      {d.showLabel && !d.dimmed && (
        <EdgeLabelRenderer>
          <div
            style={{ position: "absolute", transform: `translate(-50%, -50%) translate(${lx}px,${ly}px)`, pointerEvents: "all", cursor: "pointer" }}
            className="bg-white/95 border border-n200 rounded px-1 text-[10px] font-bold text-n800 leading-tight"
            onClick={d.onClick}
            title={`${d.ge.source_label} → ${d.ge.target_label}: ${num(d.ge.count)}人 / 遷移元 ${num(d.ge.denominator)}人`}
          >
            {pct(d.ge.rate, 0)}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { gp: GpNode };
const edgeTypes = { gp: GpEdge };

function Inner({ graph, selectedNodes, selectedEdges, onNodeClick, onEdgeClick, highlightPath, height = 560, scale, nodeOrder, compact }: Props, ref: React.Ref<GoldenPathFlowHandle>) {
  const rf = useReactFlow();
  const [hover, setHover] = useState<{ gn: GraphNode; x: number; y: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const { nodes, edges } = useMemo(() => {
    const maxRate = scale?.maxRate ?? Math.max(...graph.nodes.filter((n) => n.kind !== "outcome").map((n) => n.rate ?? 0), 0.0001);
    const maxCount = scale?.maxCount ?? Math.max(...graph.edges.map((e) => e.count), 1);
    const selN = new Set(selectedNodes.map((s) => `${s.step}:${s.label}`));
    const selE = new Set(selectedEdges.map((s) => `${s.step}:${s.source}->${s.target}`));
    const hasSel = selN.size > 0 || selE.size > 0 || (highlightPath && highlightPath.length > 0);
    const hp = highlightPath ?? [];
    const onPath = (step: number, label: string) => hp.length > 0 && hp.includes(label) && step <= graph.steps;
    const colCount = graph.steps + 1;
    const byCol = new Map<number, GraphNode[]>();
    for (const n of graph.nodes) {
      if (!byCol.has(n.step)) byCol.set(n.step, []);
      byCol.get(n.step)!.push(n);
    }
    // ordering: given order (compare) or by count desc
    for (const [k, arr] of byCol) {
      const order = nodeOrder?.[String(k)];
      if (order) arr.sort((a, b) => order.indexOf(a.label) - order.indexOf(b.label));
      else arr.sort((a, b) => (a.kind === "outcome" && b.kind === "outcome" ? outcomeRank(a.label) - outcomeRank(b.label) : b.count - a.count));
    }
    const diam = (n: GraphNode) => (n.kind === "outcome" ? 58 : Math.round(D_MIN + (D_MAX - D_MIN) * Math.sqrt(Math.min(1, (n.rate ?? 0) / maxRate))));
    const colHeights = new Map<number, number>();
    for (let k = 1; k <= colCount; k++) {
      const arr = byCol.get(k) ?? [];
      colHeights.set(k, arr.reduce((s, n) => s + diam(n) + GAP, 0));
    }
    const maxH = Math.max(...colHeights.values(), 200);
    const outNodes: Node[] = [];
    const nodeSize = new Map<string, { x: number; y: number; d: number }>();
    for (let k = 1; k <= colCount; k++) {
      const arr = byCol.get(k) ?? [];
      const cx = 80 + (k - 1) * COL_W;
      let y = HEADER_H + (maxH - (colHeights.get(k) ?? 0)) / 2;
      for (const n of arr) {
        const d = diam(n);
        const w = n.kind === "outcome" ? 132 : d;
        const x = cx - w / 2;
        nodeSize.set(n.id, { x, y, d });
        const key = `${n.step}:${n.label}`;
        const isSel = selN.has(key);
        const dimmed = !!hasSel && !isSel && !onPath(n.step, n.label) && !selectedEdgesTouch(selE, n);
        outNodes.push({
          id: n.id,
          type: "gp",
          position: { x, y },
          draggable: false,
          data: { gn: n, d, selected: isSel, dimmed, onClick: () => onNodeClick?.(n.step, n.label), onHover: (gn: GraphNode | null, e?: React.MouseEvent) => setHover(gn && e ? { gn, x: e.clientX, y: e.clientY } : null) },
        });
        y += d + GAP;
      }
      // column header
      const col = graph.columns.find((c) => c.step === k);
      outNodes.push({
        id: `h${k}`,
        type: "default",
        position: { x: cx - 70, y: 0 },
        draggable: false,
        selectable: false,
        data: { label: `${col?.label ?? `STEP ${k}`}${compact ? "" : `  ·  到達 ${num(col?.reached ?? 0)}`}` },
        style: { width: 140, background: "transparent", border: "none", boxShadow: "none", fontSize: 10.5, fontWeight: 700, color: "#5f5f6e", textAlign: "center", letterSpacing: 0.4, padding: 0 },
      });
    }
    const labelThreshold = compact ? 0.3 : 0.15;
    const outEdges: Edge<GpEdgeData>[] = graph.edges.map((e) => {
      const key = `${e.step}:${e.source_label}->${e.target_label}`;
      const isSel = selE.has(key) || (selN.has(`${e.step}:${e.source_label}`) && selN.has(`${e.step + 1}:${e.target_label}`));
      const onHp = hp.length > 0 && hp.includes(e.source_label) && hp.includes(e.target_label) && Math.abs(hp.indexOf(e.target_label) - hp.indexOf(e.source_label)) === 1;
      const dimmed = !!hasSel && !isSel && !onHp && !selN.has(`${e.step}:${e.source_label}`) && !selN.has(`${e.step + 1}:${e.target_label}`);
      const width = Math.max(1.2, 1.2 + 12 * Math.sqrt(e.count / maxCount));
      return {
        id: e.id,
        type: "gp",
        source: e.source,
        target: e.target,
        markerEnd: { type: "arrowclosed" as const, color: isSel || onHp ? "#101016" : "#8a8a98", width: 14, height: 14 },
        data: { ge: e, width, dimmed, selected: isSel || onHp, showLabel: (e.rate ?? 0) >= labelThreshold || isSel || onHp, onClick: () => onEdgeClick?.(e.step, e.source_label, e.target_label) },
      };
    });
    return { nodes: outNodes, edges: outEdges };
  }, [graph, selectedNodes, selectedEdges, highlightPath, onNodeClick, onEdgeClick, scale, nodeOrder, compact]);

  useEffect(() => {
    const t = setTimeout(() => rf.fitView({ padding: 0.08, duration: 200 }), 30);
    return () => clearTimeout(t);
  }, [graph, rf]);

  const exportWhole = useCallback(
    async (kind: "png" | "svg", filename: string) => {
      const el = wrapRef.current?.querySelector(".react-flow__viewport") as HTMLElement | null;
      if (!el) return;
      const bounds = getNodesBounds(rf.getNodes());
      const pad = 40;
      const w = Math.ceil(bounds.width + pad * 2);
      const h = Math.ceil(bounds.height + pad * 2);
      const vp = getViewportForBounds(bounds, w, h, 1, 1, pad);
      const style = { width: `${w}px`, height: `${h}px`, transform: `translate(${vp.x}px, ${vp.y}px) scale(${vp.zoom})` };
      const fn = kind === "png" ? toPng : toSvg;
      const url = await fn(el, { backgroundColor: "#ffffff", width: w, height: h, pixelRatio: 2, style, cacheBust: true });
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
    },
    [rf],
  );

  useImperativeHandle(ref, () => ({
    exportPng: (f) => exportWhole("png", f),
    exportSvg: (f) => exportWhole("svg", f),
    fit: () => rf.fitView({ padding: 0.08 }),
  }));

  return (
    <div ref={wrapRef} style={{ height }} className="relative rounded-[var(--r)] border border-n150 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnScroll
        zoomOnScroll={false}
        minZoom={0.2}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
        onPaneClick={() => setHover(null)}
      >
        <Background gap={24} color="#ececf0" />
        <Controls showInteractive={false} />
      </ReactFlow>
      {hover && (
        <div className="fixed z-50 pointer-events-none card px-3 py-2 text-[11px] shadow-lg" style={{ left: hover.x + 14, top: hover.y + 14, maxWidth: 300 }}>
          <div className="font-bold text-n1250 mb-1">{hover.gn.label}</div>
          <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-n700">
            <span>人数</span>
            <span className="num">{num(hover.gn.count)}人</span>
            <span>経験率（分母 n={num(graph.n)}）</span>
            <span className="num">{pct(hover.gn.rate)}</span>
            <span>ステップ到達者内構成比</span>
            <span className="num">{pct(hover.gn.share_of_step)}</span>
            {graph.selection && (
              <>
                <span>選択内構成比</span>
                <span className="num">{pct(hover.gn.share_of_selection)}</span>
              </>
            )}
            <span>平均発生時期</span>
            <span className="num">{days(hover.gn.avg_dn)}</span>
            <span>購入者／非購入者</span>
            <span className="num">{num(hover.gn.buyers)}／{num(hover.gn.nonbuyers)}</span>
          </div>
          {hover.gn.members && hover.gn.members.length > 0 && (
            <div className="mt-1 text-n600 border-t border-n100 pt-1">
              統合: {hover.gn.members.slice(0, 6).map((m) => `${m.label}(${m.count})`).join(", ")}
              {hover.gn.members.length > 6 ? ` …他${hover.gn.members.length - 6}` : ""}
            </div>
          )}
          {hover.gn.small_cell && <div className="chip chip-warn mt-1">5人未満：参考値</div>}
        </div>
      )}
    </div>
  );
}

function outcomeRank(l: string) {
  return l === "購入" ? 0 : l === "後続行動あり" ? 1 : 2;
}
function selectedEdgesTouch(selE: Set<string>, n: GraphNode) {
  for (const k of selE) {
    const [step, rest] = k.split(":");
    const [a, b] = rest.split("->");
    if ((Number(step) === n.step && a === n.label) || (Number(step) + 1 === n.step && b === n.label)) return true;
  }
  return false;
}

const InnerFwd = forwardRef(Inner);

export const GoldenPathFlow = forwardRef<GoldenPathFlowHandle, Props>(function GoldenPathFlow(props, ref) {
  return (
    <ReactFlowProvider>
      <InnerFwd {...props} ref={ref} />
    </ReactFlowProvider>
  );
});
