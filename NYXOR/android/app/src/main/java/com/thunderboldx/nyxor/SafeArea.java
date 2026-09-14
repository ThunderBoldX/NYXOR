package com.thunderboldx.nyxor;

import android.app.Activity;
import android.graphics.Insets;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;
import android.widget.FrameLayout;

final class SafeArea {
    static void margins(View child, int left, int top, int right, int bottom) {
        FrameLayout.LayoutParams params = (FrameLayout.LayoutParams) child.getLayoutParams();
        if (params.leftMargin != left || params.topMargin != top || params.rightMargin != right || params.bottomMargin != bottom) {
            params.setMargins(left, top, right, bottom);
            child.setLayoutParams(params);
        }
    }
    static void attach(Activity activity, View child) {
        FrameLayout root = new FrameLayout(activity);
        root.setBackgroundColor(0xff0c0b10);
        root.addView(child, new FrameLayout.LayoutParams(-1, -1));
        if (Build.VERSION.SDK_INT >= 30) activity.getWindow().setDecorFitsSystemWindows(false);
        else activity.getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        activity.setContentView(root);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                int types = WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime();
                Insets area = insets.getInsets(types);
                margins(child, area.left, area.top, area.right, area.bottom);
                return new WindowInsets.Builder(insets).setInsets(types, Insets.NONE)
                    .setInsetsIgnoringVisibility(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout(), Insets.NONE).build();
            }
            int left = insets.getSystemWindowInsetLeft(), top = insets.getSystemWindowInsetTop();
            int right = insets.getSystemWindowInsetRight(), bottom = insets.getSystemWindowInsetBottom();
            if (Build.VERSION.SDK_INT >= 28 && insets.getDisplayCutout() != null) {
                left = Math.max(left, insets.getDisplayCutout().getSafeInsetLeft());
                top = Math.max(top, insets.getDisplayCutout().getSafeInsetTop());
                right = Math.max(right, insets.getDisplayCutout().getSafeInsetRight());
                bottom = Math.max(bottom, insets.getDisplayCutout().getSafeInsetBottom());
            }
            margins(child, left, top, right, bottom);
            WindowInsets remaining = insets.replaceSystemWindowInsets(0, 0, 0, 0);
            return Build.VERSION.SDK_INT >= 28 ? remaining.consumeDisplayCutout() : remaining;
        });
        root.requestApplyInsets();
    }
}
