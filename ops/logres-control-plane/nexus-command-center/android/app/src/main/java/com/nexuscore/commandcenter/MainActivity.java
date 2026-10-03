package com.nexuscore.commandcenter;

import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.GetCredentialException;

import com.google.android.libraries.identity.googleid.GetGoogleIdOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import static com.nexuscore.commandcenter.NexusTheme.*;

/**
 * Nexus Command Center — native owner control surface.
 * Realtime authoritative telemetry over the Nexus Native Command API.
 * The app is an owner surface, never root authority: every control is a
 * governed request delivered to Lead through the backend.
 */
public final class MainActivity extends ComponentActivity implements NexusApi.SnapshotListener {

    // Google OAuth client id advertised by earlier NCC workers; the backend may
    // advertise an override through capabilities.google_client_id. If neither is
    // configured, sign-in surfaces an honest "not configured" state.
    private static final String DEFAULT_GOOGLE_CLIENT_ID =
        "488116567878-0uvf4q2u1h2oh9hbnh45sggbv0q7tidb.apps.googleusercontent.com";

    private static final String[] TABS = {"Live", "Tasks", "Approvals", "Activity", "Admin"};

    private NexusApi api;
    private LinearLayout root, content, nav;
    private TextView connPill, statePill, sessionClock;
    private LiveNexusView liveView;
    private JSONObject snapshot;
    private int tab = 0;
    private long sessionStart;
    private boolean reducedMotion;
    private boolean motionOverride;
    private final Handler ticker = new Handler(Looper.getMainLooper());
    private final List<TimerBinding> timers = new ArrayList<>();
    private String connStatus = "CONNECTING";

    private static final class TimerBinding {
        final TextView view; final Long baseMs; final String prefix;
        TimerBinding(TextView v, Long baseMs, String prefix) { view = v; this.baseMs = baseMs; this.prefix = prefix; }
    }

    // ------------------------------------------------------------ lifecycle

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        api = new NexusApi(this);
        reducedMotion = NexusTheme.reducedMotion(this);
        motionOverride = getSharedPreferences("nexus_command_center", MODE_PRIVATE)
            .getBoolean("reduce_motion", false);
        sessionStart = System.currentTimeMillis();
        if (api.configured()) showShell(); else showSetup();
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                if (tab != 0 && content != null) { tab = 0; render(); }
                else { setEnabled(false); getOnBackPressedDispatcher().onBackPressed(); }
            }
        });
        ticker.post(tickRunnable);
    }

    private final Runnable tickRunnable = new Runnable() {
        @Override public void run() {
            tick();
            ticker.postDelayed(this, 1000);
        }
    };

    @Override protected void onDestroy() {
        ticker.removeCallbacksAndMessages(null);
        if (api != null) api.destroy();
        super.onDestroy();
    }

    // ------------------------------------------------------------ setup

    private void showSetup() {
        LinearLayout panel = column(this, 0);
        panel.setGravity(Gravity.CENTER);
        panel.setPadding(dp(28), dp(40), dp(28), dp(28));
        panel.setBackgroundColor(BG);

        TextView eyebrow = label(this, "NEXUS CORE INC", 12, PURPLE);
        eyebrow.setLetterSpacing(0.24f);
        TextView title = label(this, "Command Center", 30, TEXT);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        TextView copy = label(this,
            "Native owner console for the Nexus autonomous system. Connects only to your private authoritative backend over HTTPS.",
            14, MUTED);
        panel.addView(eyebrow); panel.addView(title); panel.addView(copy, lp(10, this));

        EditText url = input("https://command.example.com", api.endpoint(), false);
        EditText tok = input("Access token (optional on loopback)", api.token(), true);
        panel.addView(url, lp(20, this));
        panel.addView(tok, lp(10, this));

        Button connect = NexusViews.actionButton(this, "Connect securely", false);
        connect.setTextColor(CYAN);
        connect.setOnClickListener(v -> {
            String e = url.getText().toString().trim();
            if (!e.startsWith("https://") && !e.startsWith("http://")) {
                Toast.makeText(this, "Use an https:// address.", Toast.LENGTH_LONG).show();
                return;
            }
            api.configure(e, tok.getText().toString());
            sessionStart = System.currentTimeMillis();
            showShell();
        });
        panel.addView(connect, lp(16, this));

        Button google = NexusViews.actionButton(this, "Sign in with Google", false);
        google.setOnClickListener(v -> googleSignIn(null));
        panel.addView(google, lp(10, this));

        TextView honest = label(this,
            "Google sign-in verifies your identity with the backend. Telemetry is never simulated — unavailable capabilities are shown as unavailable.",
            12, FAINT);
        panel.addView(honest, lp(16, this));
        setContentView(panel);
    }

    private EditText input(String hint, String value, boolean secret) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setTextColor(TEXT);
        e.setHintTextColor(FAINT);
        e.setSingleLine();
        e.setPadding(dp(14), dp(12), dp(14), dp(12));
        e.setBackground(NexusTheme.cardBg(CARD, 12, this));
        if (secret) e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        return e;
    }

    // ------------------------------------------------------------ shell

    private void showShell() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        // Header
        LinearLayout head = new LinearLayout(this);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.setPadding(dp(16), dp(12), dp(12), dp(8));
        LinearLayout titles = column(this, 0);
        TextView nexus = label(this, "NEXUS", 11, PURPLE);
        nexus.setLetterSpacing(0.28f);
        nexus.setTypeface(Typeface.DEFAULT_BOLD);
        TextView name = label(this, "Command Center", 18, TEXT);
        name.setTypeface(Typeface.DEFAULT_BOLD);
        titles.addView(nexus); titles.addView(name);
        head.addView(titles, new LinearLayout.LayoutParams(0, -2, 1));

        connPill = pill("CONNECTING", MUTED);
        statePill = pill("—", MUTED);
        head.addView(connPill, wrap(-2, dp(4)));
        head.addView(statePill, wrap(-2, dp(4)));
        sessionClock = label(this, "0s", 11, FAINT);
        sessionClock.setTypeface(Typeface.MONOSPACE);
        head.addView(sessionClock, wrap(-2, dp(6)));
        root.addView(head);

        ScrollView scroll = new ScrollView(this);
        content = column(this, 16);
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        nav = new LinearLayout(this);
        nav.setPadding(dp(8), dp(6), dp(8), dp(10));
        root.addView(nav);
        setContentView(root);
        buildNav();
        render();
        api.startStream(this);
        api.getJson("/api/snapshot?full=1", new NexusApi.JsonCallback() {
            @Override public void ok(JSONObject body) { onSnapshot(body); }
            @Override public void fail(int code, String error) { onStatus("RECONNECTING", error); }
        });
    }

    private TextView pill(String text, int color) {
        TextView v = label(this, text, 10, color);
        v.setTypeface(Typeface.DEFAULT_BOLD);
        v.setBackground(NexusTheme.pillBg(color, this));
        v.setPadding(dp(9), dp(3), dp(9), dp(3));
        return v;
    }

    private LinearLayout.LayoutParams wrap(int w, int leftDp) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(w == -2 ? -2 : w, -2);
        p.leftMargin = dp(leftDp);
        return p;
    }

    private void buildNav() {
        nav.removeAllViews();
        for (int i = 0; i < TABS.length; i++) {
            final int idx = i;
            LinearLayout cell = column(this, 4);
            cell.setGravity(Gravity.CENTER);
            TextView t = label(this, TABS[i], 11, i == tab ? PURPLE : MUTED);
            t.setTypeface(i == tab ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
            t.setGravity(Gravity.CENTER);
            cell.addView(t);
            if (i == 2) { // Approvals badge
                int pending = pendingCount();
                if (pending > 0) {
                    TextView badge = label(this, String.valueOf(pending), 9, Color.WHITE);
                    badge.setBackground(NexusTheme.pillBg(AMBER, this));
                    badge.setGravity(Gravity.CENTER);
                    badge.setPadding(dp(6), dp(1), dp(6), dp(1));
                    cell.addView(badge);
                }
            }
            cell.setOnClickListener(v -> { tab = idx; buildNav(); render(); });
            cell.setContentDescription(TABS[i] + " tab");
            nav.addView(cell, new LinearLayout.LayoutParams(0, dp(52), 1));
        }
    }

    private int pendingCount() {
        if (snapshot == null) return 0;
        JSONObject counts = snapshot.optJSONObject("counts");
        return counts == null ? 0 : counts.optInt("pending_approvals", 0);
    }

    // ------------------------------------------------------------ stream

    @Override public void onSnapshot(JSONObject snap) {
        snapshot = snap;
        connStatus = "LIVE";
        render();
    }

    @Override public void onStatus(String status, String detail) {
        connStatus = status;
        updateHeader();
        if (content != null && snapshot == null) {
            content.removeAllViews();
            if ("OFFLINE".equals(status) || "RECONNECTING".equals(status)) {
                content.addView(NexusViews.banner(this,
                    "Connection lost — retrying with backoff. " + (detail == null ? "" : detail), ORANGE));
            } else {
                TextView t = label(this, "Contacting authoritative Nexus backend…", 14, MUTED);
                t.setGravity(Gravity.CENTER);
                content.addView(t, lp(80, this));
            }
        }
    }

    private void updateHeader() {
        if (connPill == null) return;
        int color = "LIVE".equals(connStatus) ? GREEN
            : "CONNECTING".equals(connStatus) ? AMBER
            : "RECONNECTING".equals(connStatus) ? ORANGE : RED;
        connPill.setText(connStatus);
        connPill.setTextColor(color);
        connPill.setBackground(NexusTheme.pillBg(color, this));
        if (snapshot != null) {
            JSONObject ss = snapshot.optJSONObject("system_state");
            String st = ss == null ? "UNKNOWN" : ss.optString("state", "UNKNOWN");
            statePill.setText(st.replace('_', ' '));
            statePill.setTextColor(stateColor(st));
            statePill.setBackground(NexusTheme.pillBg(stateColor(st), this));
        }
    }

    private void tick() {
        if (sessionClock != null)
            sessionClock.setText(fmtElapsed(System.currentTimeMillis() - sessionStart));
        long now = System.currentTimeMillis();
        for (TimerBinding b : timers) {
            if (b.baseMs == null) continue;
            b.view.setText(b.prefix + fmtElapsed(now - b.baseMs));
        }
    }

    // ------------------------------------------------------------ render

    private void render() {
        if (content == null || connPill == null) return;
        updateHeader();
        content.removeAllViews();
        timers.clear();
        if (snapshot == null) return;
        // staleness banner
        List<String> bad = new ArrayList<>();
        JSONObject sources = snapshot.optJSONObject("sources");
        if (sources != null) {
            JSONArray names = sources.names();
            if (names != null) for (int i = 0; i < names.length(); i++) {
                JSONObject s = sources.optJSONObject(names.optString(i));
                if (s != null && !"OK".equals(s.optString("status")))
                    bad.add(s.optString("name") + " " + s.optString("status").toLowerCase(Locale.US));
            }
        }
        if (!bad.isEmpty()) {
            content.addView(NexusViews.banner(this,
                "Some sources are degraded: " + String.join(", ", bad) + ". Stale data is marked, never hidden.",
                AMBER));
        }
        if ("RECONNECTING".equals(connStatus) || "OFFLINE".equals(connStatus)) {
            content.addView(NexusViews.banner(this,
                "Realtime stream is reconnecting — showing the last authoritative snapshot.", ORANGE));
        }
        switch (tab) {
            case 0: renderLive(); break;
            case 1: renderTasks(); break;
            case 2: renderApprovals(); break;
            case 3: renderActivity(); break;
            case 4: renderAdmin(); break;
        }
    }

    // ------------------------------------------------------------ live tab

    private void renderLive() {
        content.addView(section(this, "Live Nexus"));
        liveView = new LiveNexusView(this);
        liveView.setReducedMotion(reducedMotion || motionOverride);
        liveView.setGraph(snapshot.optJSONObject("graph"));
        content.addView(liveView, new LinearLayout.LayoutParams(-1, dp(420)));

        JSONObject counts = snapshot.optJSONObject("counts");
        JSONObject ss = snapshot.optJSONObject("system_state");
        LinearLayout row = new LinearLayout(this);
        row.addView(NexusViews.metric(this, "System", ss == null ? "—" : ss.optString("state", "—").replace('_', ' ')),
            new LinearLayout.LayoutParams(0, -2, 1));
        row.addView(NexusViews.metric(this, "Working", counts == null ? "—" : String.valueOf(counts.optInt("working", -1) < 0 ? 0 : counts.optInt("working")) + "/" + (counts == null ? "?" : String.valueOf(counts.optInt("active_workers")))),
            new LinearLayout.LayoutParams(0, -2, 1));
        row.addView(NexusViews.metric(this, "Approvals", counts == null ? "—" : String.valueOf(counts.optInt("pending_approvals"))),
            new LinearLayout.LayoutParams(0, -2, 1));
        row.addView(NexusViews.metric(this, "Blocked", counts == null ? "—" : String.valueOf(counts.optInt("blocked_tasks"))),
            new LinearLayout.LayoutParams(0, -2, 1));
        content.addView(row, lp(8, this));

        if (ss != null && ss.optJSONArray("reasons") != null) {
            JSONArray reasons = ss.optJSONArray("reasons");
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < reasons.length(); i++) sb.append("• ").append(reasons.optString(i)).append("\n");
            LinearLayout c = NexusViews.card(this);
            c.addView(label(this, "Why this state", 13, TEXT));
            c.addView(label(this, sb.toString().trim(), 12, MUTED));
            content.addView(c);
        }

        // Integration / exact SHAs
        JSONObject integ = snapshot.optJSONObject("integration");
        LinearLayout ic = NexusViews.card(this);
        ic.addView(label(this, "Integration truth", 14, TEXT));
        if (integ != null) {
            ic.addView(NexusViews.kv(this, "Branch", integ.optString("branch")));
            ic.addView(NexusViews.kv(this, "Deployed SHA", integ.optString("short")));
            ic.addView(NexusViews.kv(this, "Full SHA", integ.optString("sha")));
            ic.addView(NexusViews.kv(this, "Origin sync", integ.isNull("in_sync") ? "unknown"
                : integ.optBoolean("in_sync") ? "in sync" : "DIVERGED"));
            String cand = integ.optString("candidate_sha", "");
            ic.addView(NexusViews.kv(this, "Candidate SHA", cand.isEmpty() ? "—" : cand));
        } else {
            ic.addView(NexusViews.unavailable(this, "Integration"));
        }
        content.addView(ic);

        // Workers
        JSONArray workers = snapshot.optJSONArray("workers");
        LinearLayout wc = NexusViews.card(this);
        wc.addView(label(this, "AI workers (" + snapshot.optInt("workers_total", workers == null ? 0 : workers.length())
            + " registered)", 14, TEXT));
        if (workers == null || workers.length() == 0) {
            wc.addView(label(this, "No active worker presence reported.", 12, MUTED));
        } else {
            int shown = 0;
            for (int i = 0; i < workers.length() && shown < 8; i++) {
                JSONObject w = workers.optJSONObject(i);
                if (w == null) continue;
                shown++;
                LinearLayout wr = new LinearLayout(this);
                wr.setGravity(Gravity.CENTER_VERTICAL);
                View dot = new View(this);
                dot.setBackground(NexusTheme.pillBg(stateColor(
                    "ACTIVE".equals(w.optString("state")) ? "AUTONOMOUS"
                        : "STALE".equals(w.optString("state")) ? "BLOCKED" : "IDLE"), this));
                wr.addView(dot, new LinearLayout.LayoutParams(dp(9), dp(9)));
                TextView n = label(this, "  " + w.optString("name"), 12, TEXT);
                wr.addView(n, new LinearLayout.LayoutParams(0, -2, 1));
                TextView s = label(this, w.optString("state") + " • " + w.optString("seen"), 10, MUTED);
                wr.addView(s);
                wc.addView(wr, lp(6, this));
                if (w.optString("task") != null && !w.optString("task").isEmpty() && !"null".equals(w.optString("task"))) {
                    wc.addView(label(this, "    " + w.optString("task") + " " + w.optString("progress", ""), 11, CYAN));
                }
            }
        }
        content.addView(wc);

        // Sources staleness
        JSONObject sources = snapshot.optJSONObject("sources");
        if (sources != null && sources.names() != null) {
            content.addView(section(this, "Telemetry sources"));
            HorizontalScrollView hsv = new HorizontalScrollView(this);
            hsv.setHorizontalScrollBarEnabled(false);
            LinearLayout strip = new LinearLayout(this);
            JSONArray names = sources.names();
            for (int i = 0; i < names.length(); i++) {
                JSONObject s = sources.optJSONObject(names.optString(i));
                if (s == null) continue;
                LinearLayout chip = column(this, 8);
                chip.setBackground(NexusTheme.cardBg(CARD, 10, this));
                TextView n = label(this, s.optString("name"), 10, TEXT);
                String status = s.optString("status", "?");
                TextView st = label(this, status + (s.optBoolean("cached") ? " • cached" : ""), 9,
                    stateColor(status));
                st.setTypeface(Typeface.DEFAULT_BOLD);
                chip.addView(n); chip.addView(st);
                chip.setContentDescription(s.optString("provenance", s.optString("name")) + " " + status);
                LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-2, -2);
                p.rightMargin = dp(8);
                strip.addView(chip, p);
            }
            hsv.addView(strip);
            content.addView(hsv);
        }

        // System metrics
        JSONObject sys = snapshot.optJSONObject("system");
        if (sys != null) {
            LinearLayout sc = NexusViews.card(this);
            sc.addView(label(this, "Runtime", 14, TEXT));
            sc.addView(NexusViews.kv(this, "Load/cpu", sys.isNull("load_per_cpu") ? "—"
                : String.format(Locale.US, "%.2f", sys.optDouble("load_per_cpu"))));
            sc.addView(NexusViews.kv(this, "Memory used", sys.isNull("mem_used_pct") ? "—"
                : sys.optDouble("mem_used_pct") + "%"));
            sc.addView(NexusViews.kv(this, "CPU pressure", sys.isNull("cpu_psi_avg10") ? "—"
                : String.format(Locale.US, "%.1f%%", sys.optDouble("cpu_psi_avg10"))));
            content.addView(sc);
        }

        renderMaintenanceCard();
    }

    private void renderMaintenanceCard() {
        JSONObject m = snapshot.optJSONObject("maintenance");
        LinearLayout mc = NexusViews.card(this);
        mc.addView(label(this, "External Maintenance", 14, TEXT));
        if (m != null && m.optBoolean("available")) {
            mc.addView(NexusViews.kv(this, "State", m.optString("state")));
            mc.addView(NexusViews.kv(this, "Note", m.optString("note")));
            mc.addView(NexusViews.kv(this, "Updated", m.optString("updated_at")));
        } else {
            mc.addView(NexusViews.unavailable(this, "External Maintenance status"));
        }
        content.addView(mc);
    }

    // ------------------------------------------------------------ tasks tab

    private void renderTasks() {
        content.addView(section(this, "Tasks"));
        JSONObject tasks = snapshot.optJSONObject("tasks");
        if (tasks == null) { content.addView(NexusViews.unavailable(this, "Task telemetry")); return; }
        JSONArray open = tasks.optJSONArray("open");
        if (open == null || open.length() == 0) {
            content.addView(label(this, "No open work — the autonomous queue is clear.", 14, MUTED));
        } else {
            String lastState = null;
            for (int i = 0; i < open.length(); i++) {
                JSONObject t = open.optJSONObject(i);
                if (t == null) continue;
                String st = t.optString("state", "UNKNOWN");
                if (!st.equals(lastState)) {
                    lastState = st;
                    TextView h = label(this, st.replace('_', ' '), 13, stateColor(st));
                    h.setTypeface(Typeface.DEFAULT_BOLD);
                    h.setPadding(0, dp(14), 0, dp(4));
                    content.addView(h);
                }
                content.addView(taskCard(t));
            }
        }
        JSONArray done = tasks.optJSONArray("recent_done");
        if (done != null && done.length() > 0) {
            content.addView(section(this, "Recently completed"));
            for (int i = 0; i < done.length(); i++) {
                JSONObject t = done.optJSONObject(i);
                if (t == null) continue;
                LinearLayout c = NexusViews.card(this);
                LinearLayout top = new LinearLayout(this);
                top.setGravity(Gravity.CENTER_VERTICAL);
                top.addView(label(this, t.optString("id"), 12, TEXT), new LinearLayout.LayoutParams(0, -2, 1));
                top.addView(NexusViews.statePill(this, t.optString("state", "DONE")));
                c.addView(top);
                c.addView(label(this, t.optString("summary", t.optString("title")), 12, MUTED));
                c.addView(label(this, "Updated " + t.optString("updated_at", "—"), 10, FAINT));
                content.addView(c);
            }
        }
    }

    private View taskCard(JSONObject t) {
        LinearLayout c = NexusViews.card(this);
        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        TextView id = label(this, t.optString("id"), 12, TEXT);
        id.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        top.addView(id, new LinearLayout.LayoutParams(0, -2, 1));
        top.addView(NexusViews.statePill(this, t.optString("state")));
        c.addView(top);

        c.addView(label(this, t.optString("summary", t.optString("title")), 13, MUTED));

        Integer progress = t.isNull("progress") ? null : t.optInt("progress");
        if (progress != null) {
            c.addView(NexusViews.progress(this, progress));
            c.addView(label(this, progress + "% complete", 10, FAINT));
        }

        LinearLayout meta = new LinearLayout(this);
        meta.setGravity(Gravity.CENTER_VERTICAL);
        String owner = t.optString("owner");
        if (owner != null && !owner.isEmpty() && !"null".equals(owner))
            meta.addView(label(this, "owner " + owner + "   ", 10, FAINT));
        String lane = t.optString("lane");
        if (lane != null && !lane.isEmpty() && !"null".equals(lane))
            meta.addView(label(this, lane + "   ", 10, FAINT));
        c.addView(meta, lp(4, this));

        // Elapsed timer (ticks every second)
        Long base = t.isNull("elapsed_ms") ? null : System.currentTimeMillis() - t.optLong("elapsed_ms");
        TextView timer = label(this, "⏱ " + (base == null ? "—" : fmtElapsed(System.currentTimeMillis() - base)), 12, CYAN);
        timer.setTypeface(Typeface.MONOSPACE);
        c.addView(timer);
        timers.add(new TimerBinding(timer, base, "⏱ "));

        JSONArray deps = t.optJSONArray("depends_on");
        if (deps != null && deps.length() > 0) {
            StringBuilder sb = new StringBuilder("Depends on: ");
            for (int i = 0; i < deps.length(); i++) {
                if (i > 0) sb.append(", ");
                sb.append(deps.optString(i));
            }
            c.addView(label(this, sb.toString(), 10, ORANGE));
        }
        String branch = t.optString("branch");
        if (branch != null && !branch.isEmpty() && !"null".equals(branch))
            c.addView(label(this, "⎇ " + branch, 10, FAINT));
        return c;
    }

    // ------------------------------------------------------------ approvals tab

    private void renderApprovals() {
        content.addView(section(this, "Approval Required"));
        JSONObject caps = snapshot.optJSONObject("capabilities");
        if (caps != null && !caps.optBoolean("approvals", true)) {
            content.addView(NexusViews.unavailable(this, "Approvals inbox"));
            return;
        }
        JSONObject approvals = snapshot.optJSONObject("approvals");
        JSONArray pending = approvals == null ? null : approvals.optJSONArray("pending");
        if (pending == null || pending.length() == 0) {
            LinearLayout c = NexusViews.card(this);
            c.addView(label(this, "Inbox clear", 16, TEXT));
            c.addView(label(this,
                "No gated actions are waiting for your decision. When Nexus needs an owner decision it appears here with full evidence.",
                12, MUTED));
            content.addView(c);
        } else {
            for (int i = 0; i < pending.length(); i++) {
                JSONObject a = pending.optJSONObject(i);
                if (a != null) content.addView(approvalCard(a));
            }
        }
        if (decidedCache != null && !decidedCache.isEmpty()) {
            content.addView(section(this, "Decided"));
            for (int i = 0; i < Math.min(decidedCache.size(), 8); i++)
                content.addView(decidedCard(decidedCache.get(i)));
        }
        refreshDecidedCache();
    }

    private List<JSONObject> decidedCache;
    private long decidedFetchedAt;

    private void refreshDecidedCache() {
        if (System.currentTimeMillis() - decidedFetchedAt < 15000) return;
        decidedFetchedAt = System.currentTimeMillis();
        api.getJson("/api/approvals?status=ALL", new NexusApi.JsonCallback() {
            @Override public void ok(JSONObject body) {
                JSONArray all = body.optJSONArray("approvals");
                if (all == null) return;
                List<JSONObject> decided = new ArrayList<>();
                for (int i = 0; i < all.length(); i++) {
                    JSONObject a = all.optJSONObject(i);
                    if (a != null && !"PENDING".equals(a.optString("status"))) decided.add(a);
                }
                decidedCache = decided;
                if (tab == 2) render();
            }
            @Override public void fail(int code, String error) { }
        });
    }

    private View approvalCard(JSONObject a) {
        LinearLayout c = NexusViews.card(this);
        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        TextView id = label(this, a.optString("id"), 13, AMBER);
        id.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        top.addView(id, new LinearLayout.LayoutParams(0, -2, 1));
        top.addView(NexusViews.statePill(this, "APPROVAL_REQUIRED"));
        c.addView(top);

        c.addView(NexusViews.kv(this, "Action", a.optString("action", "integrate-candidate")));
        c.addView(NexusViews.kv(this, "Reason", a.optString("reason")));
        c.addView(NexusViews.kv(this, "Scope", a.optString("scope")));
        c.addView(NexusViews.kv(this, "Risk", a.optString("risk")));
        c.addView(NexusViews.kv(this, "Exact SHA", a.optString("sha")));
        String task = a.optString("task_id");
        if (task != null && !task.isEmpty() && !"null".equals(task))
            c.addView(NexusViews.kv(this, "Task", task));

        JSONObject ev = a.optJSONObject("evidence");
        LinearLayout ec = NexusViews.card(this);
        ec.setBackground(NexusTheme.cardBg(CARD_HI, 12, this));
        ec.addView(label(this, "Evidence", 12, CYAN));
        ec.addView(label(this,
            ev != null ? ev.toString() : a.optString("evidence_summary", "No evidence attached"), 11, MUTED));
        c.addView(ec);

        String rollback = a.optString("rollback");
        c.addView(NexusViews.kv(this, "Rollback", rollback == null || rollback.isEmpty() ? "not specified" : rollback));

        Long base = a.isNull("elapsed_ms") ? null : System.currentTimeMillis() - a.optLong("elapsed_ms");
        TextView waiting = label(this, "Waiting " + (base == null ? "—" : fmtElapsed(System.currentTimeMillis() - base)), 11, AMBER);
        c.addView(waiting);
        timers.add(new TimerBinding(waiting, base, "Waiting "));

        LinearLayout row = new LinearLayout(this);
        Button approve = NexusViews.actionButton(this, "Approve", false);
        approve.setTextColor(GREEN);
        approve.setOnClickListener(v -> decideDialog(a, "approve-gate", "Approve"));
        Button decline = NexusViews.actionButton(this, "Decline", true);
        decline.setOnClickListener(v -> decideDialog(a, "reject-gate", "Decline"));
        row.addView(approve, new LinearLayout.LayoutParams(0, -2, 1));
        row.addView(decline, new LinearLayout.LayoutParams(0, -2, 1));
        c.addView(row, lp(10, this));
        return c;
    }

    private View decidedCard(JSONObject a) {
        LinearLayout c = NexusViews.card(this);
        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.addView(label(this, a.optString("id"), 12, TEXT), new LinearLayout.LayoutParams(0, -2, 1));
        String st = a.optString("status");
        top.addView(NexusViews.statePill(this, "APPROVED".equals(st) ? "DONE" : "FAILED"));
        c.addView(top);
        c.addView(label(this, st + " — " + a.optString("reason"), 12, MUTED));
        String note = a.optString("decision_note");
        if (note != null && !note.isEmpty() && !"null".equals(note))
            c.addView(label(this, "Note: " + note, 10, FAINT));
        return c;
    }

    private void decideDialog(JSONObject a, String action, String verb) {
        EditText note = new EditText(this);
        note.setHint("Decision note (optional)");
        note.setTextColor(TEXT);
        note.setHintTextColor(FAINT);
        new AlertDialog.Builder(this)
            .setTitle(verb + " " + a.optString("id") + "?")
            .setMessage("This decision is recorded in the audit log and delivered to Lead governance with the exact SHA.")
            .setView(note)
            .setNegativeButton("Cancel", null)
            .setPositiveButton(verb, (d, w) -> {
                try {
                    JSONObject payload = new JSONObject()
                        .put("action", action)
                        .put("approval_id", a.optString("id"))
                        .put("sha", a.optString("sha"))
                        .put("note", note.getText().toString());
                    api.postJson("/api/control", payload, new NexusApi.JsonCallback() {
                        @Override public void ok(JSONObject body) {
                            Toast.makeText(MainActivity.this,
                                "Decision recorded: " + body.optString("decision", "ok"), Toast.LENGTH_LONG).show();
                            render();
                        }
                        @Override public void fail(int code, String error) {
                            Toast.makeText(MainActivity.this, "Decision failed: " + error, Toast.LENGTH_LONG).show();
                        }
                    });
                } catch (Exception e) { /* json put cannot fail on strings */ }
            }).show();
    }

    // ------------------------------------------------------------ activity tab

    private void renderActivity() {
        content.addView(section(this, "Activity & audit timeline"));
        List<JSONObject> events = new ArrayList<>();
        List<JSONObject> audits = new ArrayList<>();
        JSONArray ev = snapshot.optJSONArray("events");
        if (ev != null) for (int i = 0; i < ev.length(); i++) {
            JSONObject e = ev.optJSONObject(i);
            if (e != null) events.add(e);
        }
        JSONArray au = snapshot.optJSONArray("audit");
        if (au != null) for (int i = 0; i < au.length(); i++) {
            JSONObject a = au.optJSONObject(i);
            if (a != null) audits.add(a);
        }
        if (events.isEmpty() && audits.isEmpty()) {
            content.addView(label(this, "No activity reported yet.", 14, MUTED));
        } else {
            int shown = 0;
            for (JSONObject r : audits) {
                if (shown++ >= 20) break;
                content.addView(activityRow(r, true));
            }
            for (JSONObject r : events) {
                if (shown++ >= 40) break;
                content.addView(activityRow(r, false));
            }
        }
        renderEvidence();
    }

    private View activityRow(JSONObject r, boolean isAudit) {
        LinearLayout c = NexusViews.card(this);
        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        TextView tag = label(this, isAudit ? "CONTROL" : r.optString("type", "EVENT"), 9,
            isAudit ? PURPLE : CYAN);
        tag.setTypeface(Typeface.DEFAULT_BOLD);
        tag.setBackground(NexusTheme.pillBg(isAudit ? PURPLE : CYAN, this));
        tag.setPadding(dp(6), dp(2), dp(6), dp(2));
        top.addView(tag);
        String who = isAudit ? r.optString("actor") : r.optString("sender") + "→" + r.optString("target");
        top.addView(label(this, "  " + who, 11, MUTED), new LinearLayout.LayoutParams(0, -2, 1));
        String ts = isAudit ? r.optString("ts") : "#" + r.optString("id");
        top.addView(label(this, ts, 9, FAINT));
        c.addView(top);
        String body = isAudit
            ? r.optString("action") + " → " + r.optString("state")
            : r.optString("message");
        c.addView(label(this, body, 12, TEXT));
        String detail = isAudit ? r.optString("detail") : r.optString("detail");
        if (detail != null && !detail.isEmpty() && !"null".equals(detail))
            c.addView(label(this, detail, 10, FAINT));
        String task = r.optString("task");
        if (task != null && !task.isEmpty() && !"null".equals(task))
            c.addView(label(this, "task: " + task, 10, ORANGE));
        return c;
    }

    private void renderEvidence() {
        JSONObject ev = snapshot.optJSONObject("evidence");
        if (ev == null) return;
        JSONArray verify = ev.optJSONArray("verification");
        if (verify != null && verify.length() > 0) {
            content.addView(section(this, "Independent verification"));
            for (int i = 0; i < Math.min(verify.length(), 10); i++) {
                JSONObject v = verify.optJSONObject(i);
                if (v == null) continue;
                LinearLayout c = NexusViews.card(this);
                LinearLayout top = new LinearLayout(this);
                top.setGravity(Gravity.CENTER_VERTICAL);
                String status = v.optString("status", "?");
                top.addView(NexusViews.statePill(this, "PASS".equals(status) ? "DONE" : "FAILED"));
                top.addView(label(this, "  " + v.optString("ref", "?"), 12, TEXT),
                    new LinearLayout.LayoutParams(0, -2, 1));
                c.addView(top);
                c.addView(label(this, status + " • " + v.optString("mode", "") + " • "
                    + v.optString("duration_sec", "?") + "s", 11, MUTED));
                c.addView(label(this, "sha " + v.optString("sha", "—"), 10, FAINT));
                c.addView(label(this, v.optString("ran_at", ""), 9, FAINT));
                content.addView(c);
            }
        }
        JSONArray artifacts = ev.optJSONArray("artifacts");
        if (artifacts != null && artifacts.length() > 0) {
            content.addView(section(this, "Certification artifacts"));
            for (int i = 0; i < Math.min(artifacts.length(), 12); i++) {
                JSONObject a = artifacts.optJSONObject(i);
                if (a == null) continue;
                LinearLayout c = NexusViews.card(this);
                c.addView(label(this, a.optString("name"), 12, TEXT));
                String verdict = a.optString("verdict");
                c.addView(label(this, (verdict == null || verdict.isEmpty() ? a.optString("kind") : verdict)
                    + " • " + a.optString("dir"), 10, MUTED));
                content.addView(c);
            }
        }
    }

    // ------------------------------------------------------------ admin tab

    private void renderAdmin() {
        content.addView(section(this, "Governed admin"));
        LinearLayout notice = NexusViews.banner(this,
            "This app is an owner control surface — never root authority. Every action below is a governed request delivered to Lead. It cannot bypass leases, verification, or integration gates.",
            PURPLE);
        content.addView(notice);

        JSONObject caps = snapshot.optJSONObject("capabilities");
        JSONArray allowed = caps == null ? null : caps.optJSONArray("control_requests");
        if (allowed == null) {
            content.addView(NexusViews.unavailable(this, "Governed controls"));
        } else {
            LinearLayout grid = new LinearLayout(this);
            grid.setOrientation(LinearLayout.VERTICAL);
            String[][] labels = {
                {"wake-lead", "Wake Lead"}, {"run-preflight", "Run preflight"},
                {"pause-autonomy", "Pause autonomy"}, {"resume-autonomy", "Resume autonomy"},
                {"retry-task", "Retry task"}, {"release-stale-lease", "Release stale lease"},
                {"supervisor-tick", "Supervisor tick"}, {"autonomy-cycle", "Autonomy cycle"},
                {"verify-ref", "Verify ref"}};
            for (String[] pair : labels) {
                String action = pair[0], labelTxt = pair[1];
                boolean enabled = false;
                for (int i = 0; i < allowed.length(); i++)
                    if (action.equals(allowed.optString(i))) enabled = true;
                Button b = NexusViews.actionButton(this, labelTxt, false);
                b.setEnabled(enabled);
                if (!enabled) b.setAlpha(0.4f);
                b.setOnClickListener(v -> controlDialog(action, labelTxt, false));
                grid.addView(b, lp(8, this));
            }
            content.addView(grid);
        }

        // Emergency — governed, typed confirmation
        content.addView(section(this, "Emergency (governed)"));
        LinearLayout warn = NexusViews.banner(this,
            "Emergency actions request a governed stop/revoke through the backend authority. They are audit-logged and require typed confirmation.",
            RED);
        content.addView(warn);
        Button stop = NexusViews.actionButton(this, "Emergency stop — all autonomous construction", true);
        stop.setOnClickListener(v -> controlDialog("emergency-stop", "Emergency stop", true));
        content.addView(stop, lp(8, this));
        Button revoke = NexusViews.actionButton(this, "Revoke a task lease", true);
        revoke.setOnClickListener(v -> controlDialog("revoke-lease", "Revoke lease", true));
        content.addView(revoke, lp(8, this));

        // Deployment truth
        content.addView(section(this, "Deployment"));
        JSONObject integ = snapshot.optJSONObject("integration");
        LinearLayout dc = NexusViews.card(this);
        if (integ != null) {
            dc.addView(NexusViews.kv(this, "Deployed SHA", integ.optString("sha")));
            dc.addView(NexusViews.kv(this, "Candidate SHA", integ.optString("candidate_sha", "—")));
            dc.addView(NexusViews.kv(this, "Sync", integ.isNull("in_sync") ? "unknown"
                : integ.optBoolean("in_sync") ? "origin in sync" : "DIVERGED"));
        } else dc.addView(NexusViews.unavailable(this, "Deployment"));
        content.addView(dc);

        // Supervisor / runtime ops
        JSONObject sup = snapshot.optJSONObject("supervisor");
        if (sup != null) {
            LinearLayout sc = NexusViews.card(this);
            sc.addView(label(this, "Supervisor & runtime ops", 14, TEXT));
            JSONObject runs = sup.optJSONObject("last_runs");
            if (runs != null && runs.names() != null) {
                JSONArray names = runs.names();
                for (int i = 0; i < names.length(); i++) {
                    JSONObject r = runs.optJSONObject(names.optString(i));
                    if (r == null) continue;
                    sc.addView(NexusViews.kv(this, names.optString(i),
                        (r.optBoolean("running") ? "running" : "idle") + " • rc=" + r.opt("rc")
                        + (r.optString("error").isEmpty() || "null".equals(r.optString("error")) ? "" : " • " + r.optString("error"))));
                }
            }
            JSONObject ops = snapshot.optJSONObject("operations");
            if (ops != null) {
                sc.addView(NexusViews.kv(this, "Preflight", ops.optBoolean("preflight_active") ? "ACTIVE" : "idle"));
                sc.addView(NexusViews.kv(this, "Verify farm", ops.optBoolean("verify_active") ? "ACTIVE" : "idle"));
            }
            content.addView(sc);
        }

        renderMaintenanceCard();

        // Milestones
        JSONArray ms = snapshot.optJSONArray("milestones");
        if (ms != null && ms.length() > 0) {
            content.addView(section(this, "Milestones"));
            for (int i = 0; i < ms.length(); i++) {
                JSONObject m = ms.optJSONObject(i);
                if (m == null) continue;
                LinearLayout c = NexusViews.card(this);
                LinearLayout top = new LinearLayout(this);
                top.setGravity(Gravity.CENTER_VERTICAL);
                top.addView(label(this, m.optString("title", m.optString("id")), 13, TEXT),
                    new LinearLayout.LayoutParams(0, -2, 1));
                top.addView(NexusViews.statePill(this, "DONE".equals(m.optString("status")) ? "DONE"
                    : "IN_PROGRESS".equals(m.optString("status")) ? "AUTONOMOUS" : "IDLE"));
                c.addView(top);
                content.addView(c);
            }
        }

        // Settings
        content.addView(section(this, "Connection"));
        String identity = api.googleIdentity();
        if (!identity.isEmpty())
            content.addView(label(this, "Signed in as " + identity, 12, CYAN));
        Button google = NexusViews.actionButton(this, identity.isEmpty() ? "Sign in with Google" : "Re-verify Google identity", false);
        google.setOnClickListener(v -> googleSignIn(null));
        content.addView(google, lp(6, this));
        Button motion = NexusViews.actionButton(this,
            (motionOverride ? "Enable" : "Reduce") + " motion (accessibility)", false);
        motion.setOnClickListener(v -> {
            motionOverride = !motionOverride;
            getSharedPreferences("nexus_command_center", MODE_PRIVATE).edit()
                .putBoolean("reduce_motion", motionOverride).apply();
            if (liveView != null) liveView.setReducedMotion(reducedMotion || motionOverride);
            render();
        });
        content.addView(motion, lp(8, this));
        Button reconfig = NexusViews.actionButton(this, "Change server / token", false);
        reconfig.setOnClickListener(v -> { api.stop(); showSetup(); });
        content.addView(reconfig, lp(8, this));
    }

    private void controlDialog(String action, String labelTxt, boolean emergency) {
        LinearLayout box = column(this, 4);
        EditText task = null, ref = null, note, confirm = null;
        if ("retry-task".equals(action) || "release-stale-lease".equals(action) || "revoke-lease".equals(action)) {
            task = new EditText(this);
            task.setHint("Task id (e.g. MISSION-001)");
            task.setTextColor(TEXT); task.setHintTextColor(FAINT);
            box.addView(task);
        }
        if ("verify-ref".equals(action)) {
            ref = new EditText(this);
            ref.setHint("Git ref to verify");
            ref.setTextColor(TEXT); ref.setHintTextColor(FAINT);
            box.addView(ref);
        }
        note = new EditText(this);
        note.setHint("Operator note (optional)");
        note.setTextColor(TEXT); note.setHintTextColor(FAINT);
        box.addView(note);
        String expected = null;
        if ("run-preflight".equals(action)) expected = "RUN PREFLIGHT";
        if ("emergency-stop".equals(action)) expected = "EMERGENCY STOP";
        if ("revoke-lease".equals(action)) expected = "REVOKE";
        if (expected != null) {
            confirm = new EditText(this);
            confirm.setHint("Type \"" + expected + "\" to authorize");
            confirm.setTextColor(TEXT); confirm.setHintTextColor(FAINT);
            box.addView(confirm);
        }
        final EditText fTask = task, fRef = ref, fConfirm = confirm;
        new AlertDialog.Builder(this)
            .setTitle(labelTxt)
            .setMessage(emergency
                ? "Submit a governed emergency request? Lead decides and may refuse; this app cannot force the system."
                : "Submit this governed request to Lead?")
            .setView(box)
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Submit", (d, w) -> {
                try {
                    JSONObject p = new JSONObject().put("action", action)
                        .put("note", note.getText().toString());
                    if (fTask != null) p.put("task", fTask.getText().toString().trim());
                    if (fRef != null) p.put("ref", fRef.getText().toString().trim());
                    if (fConfirm != null) p.put("confirm", fConfirm.getText().toString().trim());
                    api.postJson("/api/control", p, new NexusApi.JsonCallback() {
                        @Override public void ok(JSONObject body) {
                            Toast.makeText(MainActivity.this,
                                "REQUESTED — " + body.optString("message", ""), Toast.LENGTH_LONG).show();
                        }
                        @Override public void fail(int code, String error) {
                            Toast.makeText(MainActivity.this, "Rejected: " + error, Toast.LENGTH_LONG).show();
                        }
                    });
                } catch (Exception e) { /* strings only */ }
            }).show();
    }

    // ------------------------------------------------------------ google sign-in

    private void googleSignIn(String serverClientIdOverride) {
        String clientId = serverClientIdOverride;
        if (clientId == null && snapshot != null) {
            JSONObject caps = snapshot.optJSONObject("capabilities");
            if (caps != null) clientId = caps.optString("google_client_id", null);
        }
        if (clientId == null || clientId.isEmpty()) clientId = DEFAULT_GOOGLE_CLIENT_ID;
        GetGoogleIdOption googleOption = new GetGoogleIdOption.Builder()
            .setServerClientId(clientId)
            .setFilterByAuthorizedAccounts(false)
            .setAutoSelectEnabled(false)
            .build();
        GetCredentialRequest request = new GetCredentialRequest.Builder()
            .addCredentialOption(googleOption)
            .build();
        CredentialManager.create(this).getCredentialAsync(this, request, null, getMainExecutor(),
            new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                @Override public void onResult(GetCredentialResponse result) {
                    try {
                        GoogleIdTokenCredential g =
                            GoogleIdTokenCredential.createFrom(result.getCredential().getData());
                        String idToken = g.getIdToken();
                        api.googleSignInExchange(idToken, new NexusApi.JsonCallback() {
                            @Override public void ok(JSONObject body) {
                                String ident = body.optString("email",
                                    g.getDisplayName() == null ? "Google user" : g.getDisplayName());
                                api.setGoogleSession(body.optString("session"), ident);
                                Toast.makeText(MainActivity.this,
                                    "Verified: " + ident, Toast.LENGTH_LONG).show();
                                if (!api.configured()) return;
                                render();
                            }
                            @Override public void fail(int code, String error) {
                                Toast.makeText(MainActivity.this,
                                    "Backend did not verify the Google identity (" + error
                                    + ") — telemetry access still requires the Nexus token.",
                                    Toast.LENGTH_LONG).show();
                            }
                        });
                    } catch (Exception e) {
                        Toast.makeText(MainActivity.this, "Google identity parse failed", Toast.LENGTH_LONG).show();
                    }
                }
                @Override public void onError(GetCredentialException e) {
                    Toast.makeText(MainActivity.this,
                        "Google sign-in unavailable: " + e.getClass().getSimpleName(), Toast.LENGTH_LONG).show();
                }
            });
    }

    private int dp(int v) { return NexusTheme.dp(this, v); }
    private LinearLayout column(android.content.Context c, int pad) { return NexusTheme.column(c, pad); }
    private TextView label(android.content.Context c, String s, float sp, int color) { return NexusTheme.label(c, s, sp, color); }
    private TextView section(android.content.Context c, String s) { return NexusTheme.section(c, s); }
    private LinearLayout.LayoutParams lp(int top, android.content.Context c) { return NexusTheme.lp(top, c); }
}
