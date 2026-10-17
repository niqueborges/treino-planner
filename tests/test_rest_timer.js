globalThis.__restTimerTestPromise = (async function () {
  const api = typeof module === 'object' && module.exports
    ? require('../rest-timer.js')
    : { createRestTimerController: globalThis.RestTimerController };
  const createController = api.createRestTimerController;
  let passed = 0;
  function assert(condition, message) { if (!condition) throw new Error(message); }
  function setup(options = {}) {
    let clock = 1000;
    let callback = null;
    let cleared = 0;
    let activeCount = 0;
    let intervalId = 0;
    const intervals = {
      set(fn) { callback = fn; activeCount += 1; intervalId += 1; return intervalId; },
      clear() { if (activeCount) { activeCount -= 1; cleared += 1; } },
      tick() { if (callback) callback(); },
      advance(ms) { clock += ms; if (callback) callback(); },
      get cleared() { return cleared; },
      get activeCount() { return activeCount; }
    };
    const pulses = [];
    const events = [];
    const gainValues = [];
    let resumeCalls = 0;
    let createdAudio = null;
    class FakeAudioContext {
      constructor() { this.state = options.audioState || 'running'; this.currentTime = 0; this.sampleRate = 48000; this.destination = {}; createdAudio = this; }
      resume() { resumeCalls += 1; if (options.rejectResume) return Promise.reject(new Error('blocked')); this.state = 'running'; return Promise.resolve(); }
      createOscillator() {
        const oscillator = { frequency: { setValueAtTime() {} }, connect() {}, start() { if (options.throwStart) throw new Error('start failed'); }, stop() { pulses.push('pulse'); events.push('pulse'); } };
        return oscillator;
      }
      createGain() { return { gain: { setValueAtTime(value) { gainValues.push(value); }, linearRampToValueAtTime(value) { gainValues.push(value); }, exponentialRampToValueAtTime(value) { gainValues.push(value); } }, connect() {} }; }
    }
    const values = options.storageValues || {};
    const storage = {
      getItem(key) { return values[key] ?? null; },
      setItem(key, value) { values[key] = value; }
    };
    let finished = 0;
    let lastRemaining = null;
    const controller = createController({
      storage,
      AudioContextCtor: options.throwAudio ? function () { throw new Error('unavailable'); } : FakeAudioContext,
      now: () => clock,
      setIntervalFn: fn => intervals.set(fn),
      clearIntervalFn: () => intervals.clear(),
      onTick: seconds => { lastRemaining = seconds; },
      onFinish: () => { finished += 1; events.push('finish'); }
    });
    return { controller, intervals, pulses, events, gainValues, values, get resumeCalls() { return resumeCalls; }, get audioState() { return createdAudio && createdAudio.state; }, get finished() { return finished; }, get lastRemaining() { return lastRemaining; } };
  }

  {
    const state = setup(); state.controller.start(1); state.intervals.advance(1000); state.intervals.tick();
    await Promise.resolve();
    assert(state.finished === 1, 'timer should finish once');
    assert(state.pulses.length === 3, 'expiration should emit three pulses');
    assert(state.events.join(',') === 'pulse,pulse,pulse,finish', 'signal should start once before completion callback');
    passed += 1;
  }
  {
    const state = setup({ audioState: 'suspended' });
    state.controller.start(30);
    assert(state.resumeCalls === 1 && state.audioState === 'running', 'starting rest should synchronously request AudioContext unlock');
    assert(state.pulses.length === 0, 'unlocking audio must not play a sound at rest start');
    assert(state.intervals.activeCount === 1, 'audio unlock must preserve the active countdown');
    passed += 1;
  }
  {
    const state = setup(); state.controller.start(1); state.intervals.advance(1000);
    assert(state.gainValues.includes(0.35), 'end-of-rest signal should use the moderately increased gain');
    assert(state.pulses.length === 3, 'increased signal gain must preserve the three-pulse signal');
    passed += 1;
  }
  {
    const state = setup(); state.controller.setEnabled(false); state.controller.start(1); state.intervals.advance(1000);
    assert(state.finished === 1, 'disabled sound must not stop the timer');
    assert(state.pulses.length === 0, 'disabled sound must be silent');
    passed += 1;
  }
  {
    const state = setup({ throwAudio: true }); state.controller.start(1); state.intervals.advance(1000);
    assert(state.finished === 1, 'AudioContext failure must not interrupt timer completion');
    assert(state.lastRemaining === 0, 'timer should reach zero even if audio fails');
    passed += 1;
  }
  {
    const state = setup({ audioState: 'suspended', rejectResume: true }); state.controller.start(1); state.intervals.advance(1000);
    await Promise.resolve();
    assert(state.finished === 1, 'blocked suspended AudioContext must not interrupt timer');
    assert(state.lastRemaining === 0, 'blocked audio must still allow timer to reach zero');
    passed += 1;
  }
  {
    const state = setup(); state.controller.setEnabled(false);
    assert(state.values['tp-rest-timer-sound-enabled'] === 'false', 'preference should persist');
    const reloaded = setup({ storageValues: state.values });
    assert(reloaded.controller.isEnabled() === false, 'preference should restore on reload');
    passed += 1;
  }
  {
    const state = setup(); const result = await state.controller.testSound();
    assert(result.ok, 'direct sound test should report successful scheduling');
    assert(result.diagnostic.created && result.diagnostic.stateBeforeResume === 'running', 'test should report AudioContext creation and initial state');
    assert(result.diagnostic.stateAfterResume === 'running', 'test should report running state after resume');
    assert(result.diagnostic.sampleRate === 48000 && result.diagnostic.destination, 'test should report sample rate and destination');
    assert(result.diagnostic.scheduled && state.pulses.length === 1, 'sound test should schedule one beep, not the timer signal sequence');
    assert(result.message.includes('não confirma saída física audível'), 'test should not claim physical playback');
    passed += 1;
  }
  {
    const state = setup({ audioState: 'suspended' }); const result = await state.controller.testSound();
    assert(result.ok && result.diagnostic.stateBeforeResume === 'suspended', 'test should report suspended state before resume');
    assert(result.diagnostic.stateAfterResume === 'running', 'test should report state after resume');
    passed += 1;
  }
  {
    const state = setup({ audioState: 'suspended', rejectResume: true }); const result = await state.controller.testSound();
    assert(!result.ok && result.diagnostic.error.includes('resume do AudioContext'), 'resume exception should be returned in diagnostics');
    assert(state.pulses.length === 0, 'beep must not be scheduled when resume fails');
    passed += 1;
  }
  {
    const state = setup({ throwStart: true }); const result = await state.controller.testSound();
    assert(!result.ok && result.diagnostic.error.includes('agendamento do beep'), 'oscillator scheduling exception should be returned in diagnostics');
    passed += 1;
  }

  {
    const state = setup(); state.controller.start(30);
    assert(state.intervals.activeCount === 1, 'one timer should be active');
    state.controller.start(1);
    assert(state.intervals.activeCount === 1, 'restarting should replace, not duplicate, the timer');
    assert(state.intervals.cleared === 1, 'the previous interval should be cleared');
    state.intervals.advance(1000);
    assert(state.finished === 1, 'restarted timer should finish once');
    assert(state.intervals.activeCount === 0, 'finished timer should leave no interval active');
    passed += 1;
  }
  if (typeof console !== 'undefined') console.log(`${passed} rest timer tests passed`);
  globalThis.__restTimerTestCount = passed;
})().catch(error => { throw error; });
