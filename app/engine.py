"""Motor de reprodução: toca áudio e vídeo e "escuta" o som para os visualizadores.

Usa o QtMultimedia (que já vem com o PySide6 e traz o FFmpeg junto), então não
precisa instalar codecs. Se um dia quisermos trocar por outro motor (como o mpv),
só este arquivo muda: o resto do programa fala apenas com a classe Engine.

Equalizador: o QtMultimedia não tem equalizador, então, quando ele está ligado e a
faixa é só de áudio, o player continua decodificando (e marcando o tempo) com o som
mudo, o programa pega o som decodificado, passa pelo equalizador (equalizer.py) e
toca por uma saída de som própria. Vídeos sempre tocam direto, sem equalizador.
"""
import math
import time
from collections import deque

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import (QAudioBufferOutput, QAudioFormat, QAudioOutput, QAudioSink,
                                  QMediaDevices, QMediaMetaData, QMediaPlayer, QVideoSink)

from .equalizer import EqProcessor, soft_limit

N_BANDS = 48          # quantidade de faixas de frequência enviadas aos visualizadores
N_FFT = 2048          # tamanho da janela de análise
WAVE_POINTS = 256     # pontos da onda do osciloscópio
SINK_SECONDS = 0.25   # quanto som fica guardado na saída própria (equalizador): evita picotes
PRIME_FRAMES = 4800   # só começa a tocar com ~110 ms de som pronto


class Engine(QObject):
    positionChanged = Signal(int)       # milissegundos
    durationChanged = Signal(int)
    playingChanged = Signal(bool)
    finished = Signal()                 # a mídia chegou ao fim
    failed = Signal(str)
    hasVideoChanged = Signal(bool)
    frameReady = Signal(QImage)
    levels = Signal(object, object, float)   # faixas (0..1), onda (-1..1), força da batida
    loaded = Signal()
    notice = Signal(str)                # aviso para a barra de estado (ex.: equalizador desligado)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.sink = QVideoSink(self)
        self.player.setVideoSink(self.sink)

        fmt = QAudioFormat()
        fmt.setSampleRate(44100)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self.tap = QAudioBufferOutput(fmt, self)
        self.player.setAudioBufferOutput(self.tap)

        self.sink.videoFrameChanged.connect(self._on_frame)
        self.tap.audioBufferReceived.connect(self._on_buffer)
        self.player.positionChanged.connect(lambda v: self.positionChanged.emit(int(v)))
        self.player.durationChanged.connect(lambda v: self.durationChanged.emit(int(v)))
        self.player.hasVideoChanged.connect(lambda v: self.hasVideoChanged.emit(bool(v)))
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(lambda _e, msg: self.failed.emit(msg or "Não foi possível tocar este arquivo."))

        self.sens = 1.0
        self.simulated = False
        self._chunks = deque()
        self._next_start_us = 0
        self._pending_seek = None
        self._pending_play = True
        self._hann = np.hanning(N_FFT).astype(np.float32)
        self._edges_cache = {}
        self._bands = np.zeros(N_BANDS, dtype=np.float32)
        self._wave = np.zeros(WAVE_POINTS, dtype=np.float32)
        self._bass_hist = deque(maxlen=45)
        self._last_beat = 0.0
        self._play_started = 0.0
        self._got_audio = False
        self._last_tick = time.perf_counter()
        self._tilt = np.linspace(0, 14, N_BANDS).astype(np.float32)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

        # equalizador (saída própria)
        self.eq = EqProcessor()
        self.eq_enabled = False
        self._dsp = False                 # o caminho do equalizador está em uso nesta faixa?
        self._dsp_ok = True               # vira False se o dispositivo de som não aceitar
        self._track_is_video = False
        self._sink = None
        self._io = None
        self._rate = 44100
        self._out = bytearray()           # som já equalizado esperando para ir à saída
        self._out_frames = 0              # quadros processados desde o início
        self._written_frames = 0          # quadros já entregues à saída
        self._primed = False
        self._ended = False
        self._ended_deadline = 0.0
        self._accept_after = None         # depois de pular na música, ignora buffers antigos
        self._accept_deadline = 0.0
        self._volume = 0.0
        self._muted = False
        self._pump = QTimer(self)
        self._pump.setTimerType(Qt.TimerType.PreciseTimer)
        self._pump.setInterval(8)
        self._pump.timeout.connect(self._pump_tick)
        self.set_volume(70)

    # ------------------------------------------------------------ controle
    @property
    def playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def set_fps(self, fps: int):
        self._timer.setInterval(16 if fps >= 60 else 33)

    def load(self, path: str, autoplay: bool = True, start_ms: int = 0, video: bool = False):
        self._chunks.clear()
        self._got_audio = False
        self.simulated = False
        self._track_is_video = bool(video)
        self._dsp_clear()
        self._update_route()
        self._pending_play = autoplay
        self._pending_seek = start_ms if start_ms > 0 else None
        self.player.setSource(QUrl.fromLocalFile(path))
        if autoplay:
            self.player.play()

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def toggle(self):
        if self.playing:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self.player.stop()

    def seek(self, ms: int):
        self._chunks.clear()
        self.player.setPosition(int(ms))
        self._after_jump(ms)

    def set_volume(self, percent: int):
        # curva suave: o ouvido percebe melhor o volume assim
        self._volume = (max(0, min(100, percent)) / 100.0) ** 2
        self._apply_volume()

    def set_muted(self, muted: bool):
        self._muted = bool(muted)
        self._apply_volume()

    def is_muted(self) -> bool:
        return self._muted

    def toggle_mute(self):
        self.set_muted(not self._muted)

    def _apply_volume(self):
        """Volume e mudo valem para a saída do player (direta) ou para a saída do equalizador."""
        self.audio.setMuted(self._muted)
        self.audio.setVolume(0.0 if self._dsp else self._volume)
        if self._sink is not None:
            self._sink.setVolume(0.0 if self._muted else self._volume)

    def position(self) -> int:
        return self.player.position()

    def duration(self) -> int:
        return self.player.duration()

    def has_video(self) -> bool:
        return self.player.hasVideo()

    def video_resolution(self) -> str:
        size = self.player.metaData().value(QMediaMetaData.Key.Resolution)
        try:
            if size is not None and size.width() > 0:
                return f"{size.width()}x{size.height()}"
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------ eventos do player
    def _on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        if self._dsp:
            P = QMediaPlayer.PlaybackState
            if state == P.PausedState and self._sink is not None:
                self._sink.suspend()
            elif playing and self._sink is not None and self._sink.state().name == "SuspendedState":
                self._sink.resume()
            elif state == P.StoppedState and not self._ended:
                self._dsp_clear()
        if playing:
            self._play_started = time.perf_counter()
            self._last_tick = self._play_started
            if not self._timer.isActive():
                self._timer.start()
        self.playingChanged.emit(playing)

    def _on_status(self, status):
        S = QMediaPlayer.MediaStatus
        if status in (S.LoadedMedia, S.BufferedMedia):
            if self._pending_seek is not None:
                self.player.setPosition(self._pending_seek)
                self._after_jump(self._pending_seek)
                self._pending_seek = None
            if status == S.LoadedMedia:
                self.loaded.emit()
        elif status == S.EndOfMedia:
            if self._dsp and self._sink is not None and not self._ended:
                # deixa terminar de tocar o que o equalizador ainda tem guardado
                self._dsp_emit(self.eq.flush())
                self._ended = True
                self._ended_deadline = time.perf_counter() + SINK_SECONDS + 1.5
            else:
                self.finished.emit()
        elif status == S.InvalidMedia:
            self.failed.emit("Formato não suportado ou arquivo danificado.")

    def _on_frame(self, frame):
        if not frame.isValid():
            return
        img = frame.toImage()
        if not img.isNull():
            self.frameReady.emit(img)

    # ------------------------------------------------------------ equalizador
    def set_eq(self, enabled: bool, gains=None, preamp=None):
        """Liga/desliga o equalizador e/ou muda as faixas (dB) e a pré-amplificação."""
        if gains is not None or preamp is not None:
            self.eq.set_gains(self.eq.gains if gains is None else gains,
                              self.eq.preamp if preamp is None else preamp)
        enabled = bool(enabled)
        if enabled and not self.eq_enabled:
            self._dsp_ok = True          # liga de novo: tenta outra vez, mesmo que tenha falhado antes
        self.eq_enabled = enabled
        self._update_route()

    def _update_route(self):
        want = self.eq_enabled and self._dsp_ok and not self._track_is_video
        if want != self._dsp:
            self._dsp = want
            self._chunks.clear()
            self._dsp_clear()
            if want:
                self._accept_after = None
        self._apply_volume()

    def _dsp_clear(self):
        """Descarta a saída própria e tudo que estava em andamento nela."""
        if self._sink is not None:
            self._sink.stop()
            self._sink.deleteLater()
        self._sink = None
        self._io = None
        self._out = bytearray()
        self._out_frames = 0
        self._written_frames = 0
        self._primed = False
        self._ended = False
        self.eq.reset()
        self._pump.stop()
        if self._dsp:
            self._chunks.clear()

    def _after_jump(self, ms):
        """A música pulou para outro ponto: o som guardado e os buffers "no ar" são do lugar antigo."""
        if self._dsp:
            self._dsp_clear()
            self._accept_after = int(ms) * 1000
            self._accept_deadline = time.perf_counter() + 1.0

    def _dsp_fail(self, why):
        self._dsp_ok = False
        self.notice.emit(why)
        QTimer.singleShot(0, self._update_route)

    def _make_sink(self, rate):
        dev = QMediaDevices.defaultAudioOutput()
        fmt = QAudioFormat()
        fmt.setSampleRate(rate)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if dev.isNull() or not dev.isFormatSupported(fmt):
            return False
        sink = QAudioSink(dev, fmt, self)
        sink.setBufferSize(int(rate * 4 * SINK_SECONDS))
        io = sink.start()
        if io is None:
            sink.deleteLater()
            return False
        self._sink, self._io, self._rate = sink, io, rate
        self.eq.set_rate(rate)
        self._apply_volume()
        if not self.playing:
            sink.suspend()
        self._pump.start()
        return True

    def _dsp_feed(self, frames, rate, start_us):
        """Recebe som decodificado (quadros x canais, float), equaliza e guarda para tocar."""
        if self._accept_after is not None:
            near = start_us is not None and start_us >= 0 and \
                self._accept_after - 400_000 <= start_us <= self._accept_after + 5_000_000
            if not near and time.perf_counter() < self._accept_deadline:
                return
            self._accept_after = None
        ch = frames.shape[1]
        if ch == 1:
            frames = np.column_stack([frames[:, 0], frames[:, 0]])
        elif ch > 2:
            frames = frames[:, :2]
        if self._sink is None and not self._make_sink(rate):
            self._dsp_fail("O equalizador foi desligado: este dispositivo de som não aceitou o formato.")
            return
        self._dsp_emit(self.eq.process(frames))

    def _dsp_emit(self, y):
        if len(y) == 0:
            return
        y = soft_limit(y)
        rate = self._rate
        self._chunks.append((self._out_frames * 1_000_000 / rate, y.mean(axis=1), rate))
        while len(self._chunks) > 240:
            self._chunks.popleft()
        self._out_frames += len(y)
        self._out.extend(np.clip(y * 32767.0, -32768, 32767).astype("<i2").tobytes())
        self._got_audio = True
        if len(self._out) > rate * 4 * 4 and not self._ended:
            # a saída consome bem mais devagar do que o player entrega (não deveria acontecer):
            # recomeça do ponto atual em vez de acumular atraso
            self._dsp_clear()

    def _pump_tick(self):
        s = self._sink
        if s is None:
            return
        if s.error().name in ("OpenError", "IOError", "FatalError"):    # (por nome: o enum muda de classe entre versões)
            self._pump.stop()
            self._dsp_fail("O equalizador foi desligado: o dispositivo de som não respondeu.")
            return
        if not self._primed:
            if len(self._out) >= PRIME_FRAMES * 4 or self._ended:
                self._primed = True
            else:
                return
        if self._out:
            n = min(s.bytesFree(), len(self._out))
            n -= n % 4
            if n > 0:
                self._io.write(bytes(self._out[:n]))
                del self._out[:n]
                self._written_frames += n // 4
        if self._ended and not self._out:
            done_us = self._written_frames * 1_000_000 // max(1, self._rate)
            if s.processedUSecs() >= done_us - 40_000 or time.perf_counter() > self._ended_deadline:
                self._ended = False
                self.finished.emit()

    # ------------------------------------------------------------ análise de áudio
    def _on_buffer(self, buf):
        try:
            fmt = buf.format()
            ch = max(1, fmt.channelCount())
            rate = fmt.sampleRate() or 44100
            sf = fmt.sampleFormat()
            raw = bytes(buf.constData())
            F = QAudioFormat.SampleFormat
            if sf == F.Int16:
                x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            elif sf == F.Float:
                x = np.frombuffer(raw, dtype="<f4").astype(np.float32)
            elif sf == F.Int32:
                x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
            elif sf == F.UInt8:
                x = (np.frombuffer(raw, dtype="u1").astype(np.float32) - 128.0) / 128.0
            else:
                return
            n = (len(x) // ch) * ch
            if n == 0:
                return
            if self._dsp:
                self._dsp_feed(x[:n].reshape(-1, ch), rate, buf.startTime())
                return
            mono = x[:n].reshape(-1, ch).mean(axis=1)
            start = buf.startTime()
            if start is None or start < 0:
                start = self._next_start_us
            self._next_start_us = start + int(len(mono) * 1_000_000 / rate)
            self._chunks.append((start, mono, rate))
            self._got_audio = True
            while len(self._chunks) > 240:
                self._chunks.popleft()
        except Exception:
            pass

    def _window(self, pos_us):
        """Pega as últimas N_FFT amostras que terminam no ponto atual da música."""
        if not self._chunks:
            return None, 44100
        # descarta o que ficou muito para trás
        while len(self._chunks) > 1:
            s, m, r = self._chunks[0]
            if s + len(m) * 1_000_000 / r < pos_us - 1_500_000:
                self._chunks.popleft()
            else:
                break
        pieces, rate = [], self._chunks[0][2]
        for s, m, r in self._chunks:
            end = s + len(m) * 1_000_000 / r
            if end <= pos_us - 90_000:
                continue
            if s > pos_us:
                break
            cut = int(max(0, min(len(m), (pos_us - s) * r / 1_000_000)))
            pieces.append(m[:cut])
            rate = r
        data = np.concatenate(pieces) if pieces else None
        if data is None or len(data) < 64:
            # sem trecho exato: usa o pedaço mais próximo
            s, m, rate = min(self._chunks, key=lambda c: abs(c[0] - pos_us))
            data = m
        return data[-N_FFT:], rate

    def _band_edges(self, rate):
        if rate not in self._edges_cache:
            freqs = np.fft.rfftfreq(N_FFT, 1.0 / rate)
            top = min(16000.0, rate / 2 * 0.95)
            edges = np.geomspace(40.0, top, N_BANDS + 1)
            idx = np.searchsorted(freqs, edges)
            self._edges_cache[rate] = idx
        return self._edges_cache[rate]

    def _analyze(self, x, rate):
        if len(x) < N_FFT:
            x = np.concatenate([np.zeros(N_FFT - len(x), dtype=np.float32), x])
        spec = np.abs(np.fft.rfft(x * self._hann)) / N_FFT * 4.0
        idx = self._band_edges(rate)
        mags = np.empty(N_BANDS, dtype=np.float32)
        for i in range(N_BANDS):
            lo = idx[i]
            hi = max(idx[i + 1], lo + 1)
            mags[i] = spec[lo:hi].max()
        db = 20.0 * np.log10(mags + 1e-7) + self._tilt + 20.0 * math.log10(max(self.sens, 0.05))
        level = np.clip((db + 72.0) / 56.0, 0.0, 1.0)
        tail = x[-WAVE_POINTS * 4:]
        if len(tail) < WAVE_POINTS * 4:
            tail = np.concatenate([np.zeros(WAVE_POINTS * 4 - len(tail), dtype=np.float32), tail])
        wave = np.clip(tail.reshape(WAVE_POINTS, 4).mean(axis=1) * 1.8 * self.sens, -1.0, 1.0)
        return level.astype(np.float32), wave.astype(np.float32)

    def _simulate(self, t):
        i = np.arange(N_BANDS, dtype=np.float32)
        env = 0.35 + 0.65 * np.exp(-i / 28.0)
        level = env * (0.5 + 0.5 * np.sin(t * (1.1 + i * 0.09) + i * 0.7)) * (0.6 + 0.4 * math.sin(t * 2.1))
        wave = 0.6 * np.sin(np.linspace(0, 6 * math.pi, WAVE_POINTS) + t * 5) * (0.5 + 0.5 * math.sin(t))
        return np.clip(level, 0, 1).astype(np.float32), wave.astype(np.float32)

    def _tick(self):
        now = time.perf_counter()
        dt = max(0.001, now - self._last_tick)
        self._last_tick = now
        target, wave, beat = None, None, 0.0

        if self.playing:
            if self._dsp:      # no equalizador, "agora" é o que a saída própria está tocando
                pos_us = int(self._sink.processedUSecs()) if self._sink is not None else 0
            else:
                pos_us = self.player.position() * 1000
            if self._got_audio:
                x, rate = self._window(pos_us)
                if x is not None:
                    target, wave = self._analyze(x, rate)
            elif now - self._play_started > 1.5:
                # o sistema não entregou o áudio para análise: anima só de enfeite
                self.simulated = True
                target, wave = self._simulate(now)

        decay = 0.80 ** (dt * 30.0)
        if target is None:
            self._bands *= decay
            self._wave *= decay
        else:
            rise = target > self._bands
            self._bands = np.where(rise, self._bands + (target - self._bands) * 0.75, self._bands * decay)
            self._wave = wave

            bass = float(self._bands[:6].mean())
            avg = sum(self._bass_hist) / len(self._bass_hist) if self._bass_hist else 0.0
            self._bass_hist.append(bass)
            if bass > avg * 1.28 + 0.04 and bass > 0.3 and now - self._last_beat > 0.22:
                self._last_beat = now
                beat = min(1.0, (bass - avg) * 3.0 + 0.4)

        self.levels.emit(self._bands.copy(), self._wave.copy(), beat)

        if not self.playing and float(self._bands.max()) < 0.004:
            self._bands[:] = 0
            self._timer.stop()
