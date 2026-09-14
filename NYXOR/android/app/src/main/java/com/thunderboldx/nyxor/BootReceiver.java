package com.thunderboldx.nyxor;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (intent == null) return;
        boolean boot = Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction());
        boolean update = Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction());
        if ((!boot || !BackgroundPreferences.bootEnabled(context)) &&
                (!update || !BackgroundPreferences.wanted(context))) return;
        try {
            context.startForegroundService(new Intent(context, MinerService.class)
                .setAction(boot ? MinerService.BOOT : MinerService.RESTORE));
        } catch (RuntimeException error) {
            // Some device vendors restrict even user-enabled boot starts.
            MinerService.notifyStartFailure(context);
        }
    }
}
