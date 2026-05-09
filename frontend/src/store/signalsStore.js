// Module-level store so SignalsView state survives tab switches
let _result = null;
let _history = [];
let _position = null;

export const signalsStore = {
  get result()   { return _result; },
  set result(v)  { _result = v; },
  get history()  { return _history; },
  set history(v) { _history = v; },
  get position() { return _position; },
  set position(v){ _position = v; },
};
