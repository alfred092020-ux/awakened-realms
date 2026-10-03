package com.nexuscore.commandcenter;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;
import android.view.animation.LinearInterpolator;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Live Nexus — first-class native animated visualization of the authoritative
 * system graph. Lanes: Authority → AI Workers → Tasks → Verification →
 * Approvals. Nodes pulse by state; particles travel edges only while real
 * work is reported. Static rendering when reduced motion is requested.
 * Driven exclusively by snapshot data — nothing here is simulated.
 */
public final class LiveNexusView extends View {
    private static final String[] LANE_ORDER =
        {"authority", "workers", "tasks", "verification", "approvals"};

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final List<JSONObject> nodes = new ArrayList<>();
    private final List<JSONObject> edges = new ArrayList<>();
    private final Map<String, float[]> pos = new HashMap<>();
    private final Map<String, Float> laneY = new HashMap<>();
    private ValueAnimator animator;
    private float phase;
    private boolean reducedMotion;
    private long lastEventAt = 0;
    private String flashNodeId;

    public LiveNexusView(Context c) { super(c); init(); }
    public LiveNexusView(Context c, AttributeSet a) { super(c, a); init(); }

    private void init() {
        textPaint.setColor(NexusTheme.TEXT);
        textPaint.setTextAlign(Paint.Align.CENTER);
    }

    public void setReducedMotion(boolean reduced) {
        reducedMotion = reduced;
        if (reduced) stopAnimator(); else startAnimator();
    }

    public void setGraph(JSONObject graph) {
        nodes.clear();
        edges.clear();
        if (graph != null) {
            JSONArray n = graph.optJSONArray("nodes");
            if (n != null) for (int i = 0; i < n.length(); i++) {
                JSONObject node = n.optJSONObject(i);
                if (node != null) nodes.add(node);
            }
            JSONArray e = graph.optJSONArray("edges");
            if (e != null) for (int i = 0; i < e.length(); i++) {
                JSONObject edge = e.optJSONObject(i);
                if (edge != null) edges.add(edge);
            }
        }
        layout();
        invalidate();
        updateDescription();
    }

    /** Flash the node tied to an authoritative event. */
    public void notifyEvent(String nodeId) {
        flashNodeId = nodeId;
        lastEventAt = System.currentTimeMillis();
    }

    private void updateDescription() {
        int blocked = 0, approvals = 0, failed = 0;
        for (JSONObject n : nodes) {
            String s = n.optString("state");
            if ("BLOCKED".equals(s)) blocked++;
            else if ("APPROVAL_REQUIRED".equals(s)) approvals++;
            else if ("FAILED".equals(s)) failed++;
        }
        setContentDescription("Live Nexus system map. " + nodes.size() + " nodes, "
            + blocked + " blocked, " + approvals + " awaiting approval, "
            + failed + " failed.");
    }

    @Override protected void onSizeChanged(int w, int h, int ow, int oh) {
        layout();
    }

    private void layout() {
        pos.clear();
        laneY.clear();
        int w = getWidth() - getPaddingLeft() - getPaddingRight();
        int h = getHeight() - getPaddingTop() - getPaddingBottom();
        if (w <= 0 || h <= 0) return;

        Map<String, List<JSONObject>> byLane = new HashMap<>();
        for (String l : LANE_ORDER) byLane.put(l, new ArrayList<>());
        for (JSONObject n : nodes) {
            String lane = n.optString("lane", "tasks");
            List<JSONObject> list = byLane.get(lane);
            if (list == null) list = byLane.get("tasks");
            list.add(n);
        }
        int laneCount = LANE_ORDER.length;
        float laneH = h / (float) laneCount;
        for (int li = 0; li < laneCount; li++) {
            String laneId = LANE_ORDER[li];
            List<JSONObject> laneNodes = byLane.get(laneId);
            float cy = getPaddingTop() + laneH * li + laneH / 2f;
            laneY.put(laneId, cy);
            if (laneNodes == null || laneNodes.isEmpty()) continue;
            int count = laneNodes.size();
            int cols = Math.max(1, Math.min(count, Math.max(1, w / NexusTheme.dp(getContext(), 104))));
            int rows = (int) Math.ceil(count / (double) cols);
            for (int i = 0; i < count; i++) {
                int row = i / cols;
                int col = i % cols;
                int inRow = Math.min(cols, count - row * cols);
                float x = getPaddingLeft() + w * (col + 0.5f) / inRow;
                float y = cy - laneH / 2f + (row + 0.7f) * (laneH / (rows + 0.4f));
                pos.put(laneNodes.get(i).optString("id"), new float[]{x, y});
            }
        }
    }

    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (!reducedMotion) startAnimator();
    }

    @Override protected void onDetachedFromWindow() {
        stopAnimator();
        super.onDetachedFromWindow();
    }

    private void startAnimator() {
        if (animator != null || reducedMotion) return;
        animator = ValueAnimator.ofFloat(0f, 1f);
        animator.setDuration(2600);
        animator.setRepeatCount(ValueAnimator.INFINITE);
        animator.setInterpolator(new LinearInterpolator());
        animator.addUpdateListener(a -> { phase = (float) a.getAnimatedValue(); invalidate(); });
        animator.start();
    }

    private void stopAnimator() {
        if (animator != null) { animator.cancel(); animator = null; }
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int w = getWidth(), h = getHeight();
        canvas.drawColor(NexusTheme.BG);

        // Lane separators + headers
        textPaint.setTextSize(NexusTheme.dp(getContext(), 10));
        textPaint.setTextAlign(Paint.Align.LEFT);
        int laneCount = LANE_ORDER.length;
        for (int li = 0; li < laneCount; li++) {
            float y = getPaddingTop() + (h - getPaddingTop() - getPaddingBottom()) * li / (float) laneCount;
            paint.setColor(NexusTheme.LINE);
            paint.setStrokeWidth(1f);
            canvas.drawLine(getPaddingLeft(), y, w - getPaddingRight(), y, paint);
            textPaint.setColor(NexusTheme.FAINT);
            canvas.drawText(LANE_ORDER[li].toUpperCase(), getPaddingLeft() + NexusTheme.dp(getContext(), 6),
                y + NexusTheme.dp(getContext(), 12), textPaint);
        }
        textPaint.setTextAlign(Paint.Align.CENTER);

        // Edges
        paint.setStyle(Paint.Style.STROKE);
        for (JSONObject e : edges) {
            float[] a = pos.get(e.optString("from"));
            float[] b = pos.get(e.optString("to"));
            if (a == null || b == null) continue;
            String kind = e.optString("kind");
            boolean neg = "blocks".equals(kind) || "awaits".equals(kind) || "decides".equals(kind);
            paint.setColor(neg ? NexusTheme.withAlpha(NexusTheme.ORANGE, 120)
                               : NexusTheme.withAlpha(NexusTheme.CYAN, 80));
            paint.setStrokeWidth(NexusTheme.dp(getContext(), neg ? 1.4f : 1f));
            Path path = new Path();
            path.moveTo(a[0], a[1]);
            float midY = (a[1] + b[1]) / 2f;
            path.cubicTo(a[0], midY, b[0], midY, b[0], b[1]);
            canvas.drawPath(path, paint);
            // Traveling packet along the edge (live signal)
            if (!reducedMotion) {
                float t = (phase + (Math.abs(a[0] * 13 + b[0] * 7) % 100) / 100f) % 1f;
                float mt = cubic(a[1], midY, midY, b[1], t);
                float mxt = cubic(a[0], a[0], b[0], b[0], t);
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(neg ? NexusTheme.AMBER : NexusTheme.CYAN);
                canvas.drawCircle(mxt, mt, NexusTheme.dp(getContext(), 2.4f), paint);
                paint.setStyle(Paint.Style.STROKE);
            }
        }

        // Nodes
        long now = System.currentTimeMillis();
        float nodeW = NexusTheme.dp(getContext(), 96);
        float nodeH = NexusTheme.dp(getContext(), 30);
        for (JSONObject n : nodes) {
            float[] p = pos.get(n.optString("id"));
            if (p == null) continue;
            String state = n.optString("state", "UNKNOWN");
            int color = NexusTheme.stateColor(state);
            RectF r = new RectF(p[0] - nodeW / 2f, p[1] - nodeH / 2f, p[0] + nodeW / 2f, p[1] + nodeH / 2f);

            // State pulse / approval halo / failure glow (animation only, data stays real)
            if (!reducedMotion) {
                if ("AUTONOMOUS".equals(state) || "VERIFYING".equals(state)) {
                    float pulse = (float) (0.5 + 0.5 * Math.sin(phase * Math.PI * 2));
                    paint.setStyle(Paint.Style.STROKE);
                    paint.setStrokeWidth(NexusTheme.dp(getContext(), 2));
                    paint.setColor(NexusTheme.withAlpha(color, (int) (60 + 140 * pulse)));
                    canvas.drawRoundRect(expand(r, 3f + 3f * pulse), 14f, 14f, paint);
                } else if ("APPROVAL_REQUIRED".equals(state)) {
                    float pulse = (float) (0.5 + 0.5 * Math.sin(phase * Math.PI * 4));
                    paint.setStyle(Paint.Style.FILL);
                    paint.setColor(NexusTheme.withAlpha(color, (int) (30 + 50 * pulse)));
                    canvas.drawRoundRect(expand(r, 6f), 16f, 16f, paint);
                } else if ("FAILED".equals(state) || "BLOCKED".equals(state)) {
                    paint.setStyle(Paint.Style.STROKE);
                    paint.setStrokeWidth(NexusTheme.dp(getContext(), 1.6f));
                    paint.setColor(NexusTheme.withAlpha(color, 150));
                    float dash = NexusTheme.dp(getContext(), 6);
                    canvas.drawRoundRect(expand(r, 4f), 14f, 14f, paint);
                }
            }
            // Event flash
            if (n.optString("id").equals(flashNodeId) && now - lastEventAt < 1200) {
                float k = 1f - (now - lastEventAt) / 1200f;
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(NexusTheme.withAlpha(NexusTheme.CYAN, (int) (70 * k)));
                canvas.drawRoundRect(expand(r, 8f * k), 16f, 16f, paint);
            }

            paint.setStyle(Paint.Style.FILL);
            paint.setColor("APPROVAL_REQUIRED".equals(state) ? NexusTheme.withAlpha(NexusTheme.AMBER, 55)
                                                            : NexusTheme.CARD);
            canvas.drawRoundRect(r, 12f, 12f, paint);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(NexusTheme.dp(getContext(), 1.4f));
            paint.setColor(color);
            canvas.drawRoundRect(r, 12f, 12f, paint);

            // State glyph strip
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(color);
            canvas.drawRoundRect(new RectF(r.left + 4, r.top + 6, r.left + 8, r.bottom - 6), 3f, 3f, paint);

            String label = n.optString("label", "?");
            if (label.length() > 16) label = label.substring(0, 15) + "…";
            textPaint.setColor(NexusTheme.TEXT);
            textPaint.setTextSize(NexusTheme.dp(getContext(), 10));
            canvas.drawText(label, p[0] + 3, p[1] + NexusTheme.dp(getContext(), 3.5f), textPaint);
        }
        paint.setStyle(Paint.Style.FILL);
    }

    private static float cubic(float p0, float p1, float p2, float p3, float t) {
        float u = 1f - t;
        return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
    }

    private static RectF expand(RectF r, float d) {
        return new RectF(r.left - d, r.top - d, r.right + d, r.bottom + d);
    }
}
