(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.RestTimerController = api.createRestTimerController;
})(globalThis, function () {
  const STORAGE_KEY = 'tp-rest-timer-sound-enabled';

  function createRestTimerController(options = {}) {
    const storage = options.storage;
    const AudioContextCtor = options.AudioContextCtor;
    const setIntervalFn = options.setIntervalFn || setInterval;
    const clearIntervalFn = options.clearIntervalFn || clearInterval;
    const now = options.now || Date.now;
    const onTick = options.onTick || function () {};
    const onFinish = options.onFinish || function () {};
    let context = null;
    let unlockPromise = null;
    let intervalId = null;
    let deadline = 0;
    let finished = false;
    let enabled = true;

    try {
      const saved = storage && storage.getItem(STORAGE_KEY);
      if (saved === 'false') enabled = false;
    } catch (_) {}

    function getContext() {
      if (!context && AudioContextCtor) context = new AudioContextCtor();
      return context;
    }

    function primeAudio() {
      if (!enabled) return Promise.resolve(false);
      try {
        const audio = getContext();
        if (!audio) return Promise.resolve(false);
        if (audio.state === 'running') {
          unlockPromise = Promise.resolve(true);
          return unlockPromise;
        }
        if (typeof audio.resume !== 'function') {
          unlockPromise = Promise.resolve(false);
          return unlockPromise;
        }
        // Call resume synchronously from the user's Concluir série click.
        const resume = audio.resume();
        unlockPromise = Promise.resolve(resume).then(function () {
          const running = audio.state === 'running';
          if (!running && typeof console !== 'undefined') console.warn('[RestTimer audio] AudioContext não ficou running após resume()', audio.state);
          return running;
        }, function (error) {
          if (typeof console !== 'undefined') console.warn('[RestTimer audio] resume() falhou ao iniciar o descanso', error);
          return false;
        });
        return unlockPromise;
      } catch (error) {
        if (typeof console !== 'undefined') console.warn('[RestTimer audio] não foi possível desbloquear o AudioContext ao iniciar o descanso', error);
        unlockPromise = Promise.resolve(false);
        return unlockPromise;
      }
    }

    async function playSignal() {
      if (!enabled) return false;
      try {
        const audio = getContext();
        if (!audio) return false;
        if (audio.state !== 'running' && unlockPromise) await unlockPromise;
        if (audio.state !== 'running' && typeof audio.resume === 'function') await audio.resume();
        if (!enabled) return false;
        if (audio.state && audio.state !== 'running') return false;
        const frequencies = [880, 1046, 880];
        const startAt = audio.currentTime || 0;
        frequencies.forEach(function (frequency, index) {
          const oscillator = audio.createOscillator();
          const gain = audio.createGain();
          const start = startAt + index * 0.22;
          oscillator.type = 'sine';
          oscillator.frequency.setValueAtTime(frequency, start);
          gain.gain.setValueAtTime(0.0001, start);
          gain.gain.linearRampToValueAtTime(0.35, start + 0.015);
          gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.17);
          oscillator.connect(gain);
          gain.connect(audio.destination);
          oscillator.start(start);
          oscillator.stop(start + 0.18);
        });
        return true;
      } catch (_) {
        return false;
      }
    }

    function setEnabled(value) {
      enabled = Boolean(value);
      try { if (storage) storage.setItem(STORAGE_KEY, String(enabled)); } catch (_) {}
      return enabled;
    }

    async function testSound() {
      const diagnostic = {
        requested: true,
        created: false,
        stateBeforeResume: null,
        stateAfterResume: null,
        destination: null,
        sampleRate: null,
        scheduled: false,
        error: null
      };
      let stage = 'preparação';
      function log(level, label, value) {
        if (typeof console !== 'undefined' && typeof console[level] === 'function') {
          console[level]('[RestTimer audio diagnostic]', label, value);
        }
      }
      function destinationInfo(destination) {
        if (!destination) return null;
        return {
          type: destination.constructor && destination.constructor.name || typeof destination,
          channelCount: destination.channelCount ?? null,
          maxChannelCount: destination.maxChannelCount ?? null,
          numberOfInputs: destination.numberOfInputs ?? null,
          numberOfOutputs: destination.numberOfOutputs ?? null
        };
      }
      function result(ok, message) {
        return { ok: ok, message: message, diagnostic: diagnostic };
      }

      if (!enabled) {
        diagnostic.error = 'Som desativado nas preferências.';
        log('warn', 'teste não executado', diagnostic.error);
        return result(false, diagnostic.error);
      }

      try {
        stage = 'criação do AudioContext';
        const audio = getContext();
        diagnostic.created = Boolean(audio);
        if (!audio) throw new Error('AudioContext não está disponível neste navegador.');
        diagnostic.stateBeforeResume = audio.state || 'não informado';
        diagnostic.destination = destinationInfo(audio.destination);
        diagnostic.sampleRate = audio.sampleRate ?? null;
        log('info', 'contexto criado/localizado', {
          created: diagnostic.created,
          stateBeforeResume: diagnostic.stateBeforeResume,
          destination: diagnostic.destination,
          sampleRate: diagnostic.sampleRate
        });

        stage = 'resume do AudioContext';
        if (audio.state !== 'running') {
          log('info', 'chamando resume()', { stateBeforeResume: audio.state });
          await audio.resume();
        }
        diagnostic.stateAfterResume = audio.state || 'não informado';
        log('info', 'resultado de resume()', { stateAfterResume: diagnostic.stateAfterResume });
        if (audio.state !== 'running') {
          throw new Error(`AudioContext não ficou running (estado: ${diagnostic.stateAfterResume}).`);
        }

        stage = 'agendamento do beep';
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        const startAt = audio.currentTime;
        const endAt = startAt + 0.5;
        const params = {
          waveform: 'sine',
          frequencyHz: 440,
          gain: 0.5,
          durationSeconds: 0.5,
          startAt: startAt,
          stopAt: endAt,
          destination: diagnostic.destination,
          sampleRate: diagnostic.sampleRate
        };
        oscillator.type = params.waveform;
        oscillator.frequency.setValueAtTime(params.frequencyHz, startAt);
        gain.gain.setValueAtTime(0.5, startAt);
        gain.gain.setValueAtTime(0.5, endAt - 0.04);
        gain.gain.linearRampToValueAtTime(0.0001, endAt);
        oscillator.connect(gain);
        gain.connect(audio.destination);
        log('info', 'parâmetros do beep simples', params);
        oscillator.start(startAt);
        oscillator.stop(endAt);
        diagnostic.scheduled = true;
        log('info', 'beep agendado; o navegador não confirma saída física audível', {
          state: audio.state,
          scheduled: diagnostic.scheduled,
          parameters: params
        });
        return result(true, `AudioContext ${audio.state}; sampleRate ${diagnostic.sampleRate} Hz; destino ${diagnostic.destination.type}; beep de 440 Hz agendado por 0,5 s, ganho 0,5. O navegador não confirma saída física audível.`);
      } catch (error) {
        diagnostic.error = `${stage}: ${error && error.message || String(error)}`;
        diagnostic.stateAfterResume = diagnostic.stateAfterResume || (context && context.state) || null;
        log('error', 'falha no teste de áudio', { error: diagnostic.error, diagnostic: diagnostic });
        return result(false, `Falha no áudio — ${diagnostic.error}. Estado: ${diagnostic.stateAfterResume || 'indisponível'}; sampleRate: ${diagnostic.sampleRate ?? 'indisponível'}; destino: ${diagnostic.destination?.type || 'indisponível'}.`);
      }
    }

    function tick() {
      if (intervalId === null || finished) return;
      const seconds = Math.max(0, Math.ceil((deadline - now()) / 1000));
      try { onTick(seconds); } catch (_) {}
      if (seconds !== 0) return;
      clearIntervalFn(intervalId);
      intervalId = null;
      finished = true;
      void playSignal();
      try { onFinish(); } catch (_) {}
    }

    function start(seconds) {
      stop();
      const duration = Math.max(0, Number(seconds) || 0);
      finished = false;
      primeAudio();
      deadline = now() + duration * 1000;
      intervalId = {};
      tick();
      if (!finished) intervalId = setIntervalFn(tick, 200);
    }

    function stop() {
      if (intervalId !== null && intervalId !== undefined) clearIntervalFn(intervalId);
      intervalId = null;
      finished = false;
    }

    return {
      start: start,
      stop: stop,
      setEnabled: setEnabled,
      isEnabled: function () { return enabled; },
      testSound: testSound
    };
  }

  return { createRestTimerController: createRestTimerController };
});
