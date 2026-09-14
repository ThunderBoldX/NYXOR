package com.thunderboldx.nyxor;

import android.app.*;
import android.content.*;
import android.os.*;
import org.json.JSONObject;
import java.util.concurrent.*;

public class MinerService extends Service {
    static final String BOOT = "NYXOR_BOOT", RESTORE = "NYXOR_RESTORE", STOP = "STOP", RESTART = "RESTART";
    static final String CHANNEL = "nyxor-farming";
    // Serialize old-service teardown and new-service startup in the same process.
    private static final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();
    private PowerManager.WakeLock wakeLock;
    private volatile boolean stopping;
    private boolean started;
    private Future<?> monitor;
    private final BroadcastReceiver screenReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (!stopping && started) executor.execute(() -> refreshStatus());
        }
    };

    static void createChannel(Context context) {
        NotificationChannel channel = new NotificationChannel(CHANNEL, "NYXOR farming", NotificationManager.IMPORTANCE_LOW);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        channel.setShowBadge(false);
        context.getSystemService(NotificationManager.class).createNotificationChannel(channel);
    }
    static void notifyStartFailure(Context context) {
        createChannel(context);
        boolean en = BackgroundPreferences.english(context);
        PendingIntent open = PendingIntent.getActivity(context, 0, new Intent(context, MainActivity.class),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        try {
            context.getSystemService(NotificationManager.class).notify(72,
                new Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_moon_status)
                    .setContentTitle("NYXOR").setContentIntent(open).setAutoCancel(true)
                    .setContentText(en ? "Open NYXOR to resume farming" : "Відкрий NYXOR, щоб відновити фарм").build());
        } catch (SecurityException ignored) {}
    }
    @Override public void onCreate() {
        super.onCreate();
        createChannel(this);
        wakeLock = getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "NYXOR:Miner");
        wakeLock.setReferenceCounted(false);
        IntentFilter screen = new IntentFilter(Intent.ACTION_SCREEN_ON);
        screen.addAction(Intent.ACTION_USER_PRESENT);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(screenReceiver, screen, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(screenReceiver, screen);
    }
    Notification notification(JSONObject status) {
        boolean en = BackgroundPreferences.english(this);
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1, new Intent(this, MinerService.class).setAction(STOP), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder builder = new Notification.Builder(this, CHANNEL)
            .setContentTitle(status.optString("title", "NYXOR"))
            .setContentText(status.optString("text", en ? "Starting…" : "Запускаємо…"))
            .setStyle(new Notification.BigTextStyle().bigText(status.optString("details", status.optString("text"))))
            .setVisibility(Notification.VISIBILITY_PUBLIC).setCategory(Notification.CATEGORY_SERVICE)
            .setOnlyAlertOnce(true).setShowWhen(false)
            .setSmallIcon(R.drawable.ic_moon_status).setContentIntent(open).setOngoing(true)
            .addAction(new Notification.Action.Builder(null, en ? "Stop" : "Зупинити", stop).build());
        if (!status.isNull("progress")) builder.setProgress(100, Math.max(0, Math.min(100, status.optInt("progress"))), false);
        return builder.build();
    }
    // Local lifecycle tests override this boundary instead of loading Python.
    protected String engine(String payload) throws Exception { return Engine.requestRuntime(this, payload); }

    @Override public synchronized int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? RESTORE : intent.getAction();
        if (STOP.equals(action)) {
            BackgroundPreferences.setWanted(this, false);
            stopping = true;
            stopSelf();
            return START_NOT_STICKY;
        }
        if ((RESTORE.equals(action) && !BackgroundPreferences.wanted(this)) ||
                (BOOT.equals(action) && !BackgroundPreferences.bootEnabled(this))) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (stopping) return START_NOT_STICKY;
        started = true;
        BackgroundPreferences.setWanted(this, true);
        startForeground(71, notification(new JSONObject()));
        wakeLock.acquire(10 * 60 * 1000L);
        getSystemService(NotificationManager.class).cancel(72);
        executor.execute(() -> {
            if (stopping) return;
            try {
                if (RESTART.equals(action)) engine("{\"action\":\"stop\"}");
                JSONObject result = new JSONObject(engine("{\"action\":\"start\"}"));
                if (!result.optBoolean("ok")) { finishFarming(true); return; }
                synchronized (this) {
                    if (!stopping && monitor == null) monitor = executor.scheduleWithFixedDelay(this::refreshStatus, 0, 15, TimeUnit.SECONDS);
                }
            } catch (Exception error) { finishFarming(true); }
        });
        return START_STICKY;
    }
    private synchronized void finishFarming(boolean failed) {
        if (stopping) return;
        BackgroundPreferences.setWanted(this, false);
        stopping = true;
        if (failed) notifyStartFailure(this);
        stopSelf();
    }
    private void refreshStatus() {
        if (stopping) return;
        try {
            JSONObject data = new JSONObject(engine("{\"action\":\"snapshot\"}")).getJSONObject("data");
            if (stopping) return;
            if (!data.optBoolean("running")) { finishFarming(!data.optString("error").isEmpty()); return; }
            synchronized (this) {
                if (stopping) return;
                wakeLock.acquire(10 * 60 * 1000L);
                JSONObject status = data.optJSONObject("notification");
                getSystemService(NotificationManager.class).notify(71, notification(status == null ? new JSONObject() : status));
            }
        } catch (Exception ignored) {}
    }
    @Override public synchronized void onDestroy() {
        stopping = true;
        unregisterReceiver(screenReceiver);
        if (monitor != null) monitor.cancel(false);
        // Preserve 'wanted' after system teardown; explicit stop cleared it earlier.
        executor.execute(() -> { try { engine("{\"action\":\"stop\"}"); } catch (Exception ignored) {} });
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
