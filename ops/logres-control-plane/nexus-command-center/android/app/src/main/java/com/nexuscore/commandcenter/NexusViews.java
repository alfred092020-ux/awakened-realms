package com.nexuscore.commandcenter;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import static com.nexuscore.commandcenter.NexusTheme.*;

/** Reusable native widgets for tab builders. */
final class NexusViews {

    static LinearLayout card(Context c) {
        LinearLayout v = NexusTheme.column(c, 14);
        v.setBackground(NexusTheme.cardBg(CARD, 16, c));
        v.setLayoutParams(NexusTheme.lp(8, c));
        return v;
    }

    static TextView statePill(Context c, String state) {
        int color = stateColor(state);
        TextView v = label(c, state == null ? "UNKNOWN" : state.replace('_', ' '), 10, color);
        v.setTypeface(Typeface.DEFAULT_BOLD);
        v.setBackground(NexusTheme.pillBg(color, c));
        int hp = dp(c, 10), vp = dp(c, 4);
        v.setPadding(hp, vp, hp, vp);
        return v;
    }

    static LinearLayout metric(Context c, String key, String value) {
        LinearLayout x = NexusTheme.column(c, 10);
        x.setBackground(NexusTheme.cardBg(CARD, 14, c));
        TextView k = label(c, key.toUpperCase(java.util.Locale.US), 9, FAINT);
        k.setLetterSpacing(0.08f);
        TextView v = label(c, value, 20, TEXT);
        v.setTypeface(Typeface.DEFAULT_BOLD);
        x.addView(k);
        x.addView(v);
        return x;
    }

    static LinearLayout kv(Context c, String key, String value) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        TextView k = label(c, key, 12, MUTED);
        TextView v = label(c, value == null || value.isEmpty() ? "—" : value, 12, TEXT);
        v.setTypeface(Typeface.MONOSPACE);
        row.addView(k, new LinearLayout.LayoutParams(dp(c, 110), -2));
        row.addView(v, new LinearLayout.LayoutParams(0, -2, 1));
        return row;
    }

    static TextView unavailable(Context c, String what) {
        TextView v = label(c, what + " — unavailable from authoritative backend.", 13, FAINT);
        v.setPadding(dp(c, 2), dp(c, 6), dp(c, 2), dp(c, 6));
        return v;
    }

    static View progress(Context c, Integer pct) {
        LinearLayout wrap = new LinearLayout(c);
        ProgressBar bar = new ProgressBar(c, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setProgress(pct == null ? 0 : Math.max(0, Math.min(100, pct)));
        bar.setIndeterminate(pct == null);
        bar.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(c, 6)));
        wrap.addView(bar);
        return wrap;
    }

    static android.widget.Button actionButton(Context c, String label, boolean danger) {
        android.widget.Button b = new android.widget.Button(c);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextColor(danger ? RED : TEXT);
        b.setBackground(NexusTheme.cardBg(danger ? Color.rgb(46, 20, 24) : CARD_HI, 12, c));
        b.setMinHeight(dp(c, 48));
        return b;
    }

    static LinearLayout banner(Context c, String text, int color) {
        LinearLayout b = NexusTheme.column(c, 10);
        GradientDrawable g = new GradientDrawable();
        g.setColor(withAlpha(color, 32));
        g.setCornerRadius(dp(c, 10));
        g.setStroke(dp(c, 1), withAlpha(color, 120));
        b.setBackground(g);
        TextView t = label(c, text, 12, color);
        b.addView(t);
        return b;
    }

    static View divider(Context c) {
        View v = new View(c);
        v.setBackgroundColor(LINE);
        v.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(c, 1)));
        return v;
    }
}
