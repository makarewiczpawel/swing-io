const INITIAL = [
  { role: "assistant", content: "Cześć! Jestem Twoim asystentem do analizy S&P 500. Możesz zapytać mnie o aktualny rynek, sygnały, VIX, poziomy wsparcia/oporu lub cokolwiek związanego ze swingiem." }
];

let _messages = [...INITIAL];

export const chatStore = {
  get messages()   { return _messages; },
  set messages(v)  { _messages = v; },
  reset()          { _messages = [...INITIAL]; },
};
