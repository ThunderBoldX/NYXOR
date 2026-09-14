package com.thunderboldx.nyxor;

import android.app.Notification;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import org.json.JSONObject;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.android.controller.ServiceController;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 28)
public class BackgroundTests {
    private Context context;
    @Before public void setup() {
        context = RuntimeEnvironment.getApplication();
        context.getSharedPreferences("nyxor-background", Context.MODE_PRIVATE).edit().clear().commit();
    }
    @Test public void bootDoesNothingUntilEnabled() throws Exception {
        new BootReceiver().onReceive(context, new Intent(Intent.ACTION_BOOT_COMPLETED));
        assertNull(shadowOf(RuntimeEnvironment.getApplication()).getNextStartedService());
        BackgroundPreferences.sync(context, new JSONObject().put("launch_on_boot", true));
        new BootReceiver().onReceive(context, new Intent(Intent.ACTION_BOOT_COMPLETED));
        Intent started = shadowOf(RuntimeEnvironment.getApplication()).getNextStartedService();
        assertEquals(MinerService.BOOT, started.getAction());
        assertEquals(MinerService.class.getName(), started.getComponent().getClassName());
    }
    @Test public void disabledBootAndUnrelatedBroadcastsCannotStartFarming() throws Exception {
        BackgroundPreferences.sync(context, new JSONObject().put("launch_on_boot", true));
        BackgroundPreferences.sync(context, new JSONObject().put("launch_on_boot", false));
        new BootReceiver().onReceive(context, new Intent(Intent.ACTION_BOOT_COMPLETED));
        new BootReceiver().onReceive(context, new Intent("unrelated"));
        assertNull(shadowOf(RuntimeEnvironment.getApplication()).getNextStartedService());
    }
    @Test public void updateOnlyRestoresAnActiveSession() {
        new BootReceiver().onReceive(context, new Intent(Intent.ACTION_MY_PACKAGE_REPLACED));
        assertNull(shadowOf(RuntimeEnvironment.getApplication()).getNextStartedService());
        BackgroundPreferences.setWanted(context, true);
        new BootReceiver().onReceive(context, new Intent(Intent.ACTION_MY_PACKAGE_REPLACED));
        assertEquals(MinerService.RESTORE, shadowOf(RuntimeEnvironment.getApplication()).getNextStartedService().getAction());
    }
    public static class FakeService extends MinerService {
        final CountDownLatch stopped = new CountDownLatch(1);
        @Override protected String engine(String payload) {
            if (payload.contains("stop")) stopped.countDown();
            return "{\"ok\":true,\"data\":{\"running\":true,\"notification\":{\"title\":\"NYXOR\",\"text\":\"Rust\"}}}";
        }
    }
    private void destroy(ServiceController<FakeService> controller) throws Exception {
        controller.destroy();
        assertTrue(controller.get().stopped.await(5, TimeUnit.SECONDS));
    }
    @Test public void systemRecreationPreservesWantedButStopCancelsIt() throws Exception {
        ServiceController<FakeService> first = Robolectric.buildService(FakeService.class).create();
        assertEquals(Service.START_STICKY, first.get().onStartCommand(new Intent(), 0, 1));
        destroy(first);
        assertTrue(BackgroundPreferences.wanted(context));
        ServiceController<FakeService> second = Robolectric.buildService(FakeService.class).create();
        assertEquals(Service.START_STICKY, second.get().onStartCommand(null, 0, 1));
        assertEquals(Service.START_NOT_STICKY, second.get().onStartCommand(new Intent().setAction(MinerService.STOP), 0, 2));
        assertFalse(BackgroundPreferences.wanted(context));
        destroy(second);
        ServiceController<FakeService> third = Robolectric.buildService(FakeService.class).create();
        assertEquals(Service.START_NOT_STICKY, third.get().onStartCommand(null, 0, 1));
        destroy(third);
    }
    @Test public void serviceRejectsBootWhenSwitchIsOff() throws Exception {
        ServiceController<FakeService> controller = Robolectric.buildService(FakeService.class).create();
        assertEquals(Service.START_NOT_STICKY, controller.get().onStartCommand(new Intent().setAction(MinerService.BOOT), 0, 1));
        assertFalse(BackgroundPreferences.wanted(context));
        destroy(controller);
    }
    @Test public void notificationShowsPublicProgressAndHasStopAction() throws Exception {
        ServiceController<FakeService> controller = Robolectric.buildService(FakeService.class).create();
        Notification notification = controller.get().notification(new JSONObject()
            .put("title", "NYXOR · Фарм працює").put("text", "Rust · streamer · 75%")
            .put("details", "Drop · 75% · 45/60 хв").put("progress", 75));
        assertEquals(Notification.VISIBILITY_PUBLIC, notification.visibility);
        assertEquals(75, notification.extras.getInt(Notification.EXTRA_PROGRESS));
        assertEquals("Drop · 75% · 45/60 хв", notification.extras.getCharSequence(Notification.EXTRA_BIG_TEXT).toString());
        assertEquals(MinerService.STOP, shadowOf(notification.actions[0].actionIntent).getSavedIntent().getAction());
        assertTrue((notification.flags & Notification.FLAG_ONGOING_EVENT) != 0);
        destroy(controller);
    }
    @Test public void buttonsAndGesturesResizeTheViewportInsteadOfPaddingItsContents() {
        android.widget.FrameLayout root = new android.widget.FrameLayout(context);
        android.view.View web = new android.view.View(context);
        root.addView(web, new android.widget.FrameLayout.LayoutParams(-1, -1));
        for (int bottom : new int[]{48, 24, 300, 0}) {
            SafeArea.margins(web, 0, 24, 0, bottom);
            root.measure(android.view.View.MeasureSpec.makeMeasureSpec(360, android.view.View.MeasureSpec.EXACTLY),
                android.view.View.MeasureSpec.makeMeasureSpec(800, android.view.View.MeasureSpec.EXACTLY));
            root.layout(0, 0, 360, 800);
            assertEquals(800 - bottom, web.getBottom());
            assertEquals(24, web.getTop());
            assertEquals(0, web.getPaddingBottom());
        }
    }
}
