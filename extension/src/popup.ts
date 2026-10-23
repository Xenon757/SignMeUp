// The toolbar popup: one switch for signing YouTube videos, remembered across devices.
const box = document.getElementById('enabled') as HTMLInputElement;
chrome.storage.sync.get({ enabled: true }).then(({ enabled }) => { box.checked = enabled !== false; });
box.addEventListener('change', () => chrome.storage.sync.set({ enabled: box.checked }));
