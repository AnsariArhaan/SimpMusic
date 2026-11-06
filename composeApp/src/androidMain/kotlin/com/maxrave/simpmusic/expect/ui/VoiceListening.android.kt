package com.maxrave.simpmusic.expect.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.maxrave.media3.voice.VoiceListenService
import com.maxrave.simpmusic.ui.component.SettingGroup
import com.maxrave.simpmusic.ui.component.SettingItem
import org.jetbrains.compose.resources.stringResource
import simpmusic.composeapp.generated.resources.Res
import simpmusic.composeapp.generated.resources.voice_listen_section
import simpmusic.composeapp.generated.resources.voice_listen_subtitle
import simpmusic.composeapp.generated.resources.voice_listen_title

@Composable
actual fun VoiceListeningSettingGroup() {
    val context = LocalContext.current
    val running by VoiceListenService.running.collectAsStateWithLifecycle()
    val micLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                ContextCompat.startForegroundService(context, VoiceListenService.startIntent(context))
            }
        }
    SettingGroup(title = stringResource(Res.string.voice_listen_section)) {
        SettingItem(
            title = stringResource(Res.string.voice_listen_title),
            subtitle = stringResource(Res.string.voice_listen_subtitle),
            switch =
                running to { checked ->
                    if (checked) {
                        if (
                            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                            PackageManager.PERMISSION_GRANTED
                        ) {
                            ContextCompat.startForegroundService(context, VoiceListenService.startIntent(context))
                        } else {
                            micLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    } else {
                        context.startService(VoiceListenService.stopIntent(context))
                    }
                },
        )
    }
}
