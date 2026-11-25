window.FACTS = {
 "team": "Aura entertainment",
 "total": {
  "nodes": 134,
  "claims": 563,
  "tasks": 112,
  "loops": 56,
  "units": 656,
  "covered": 656,
  "scan": 123
 },
 "train": [
  {
   "id": "latyshova",
   "title": "Латышова (1991), гл. V §17–20",
   "set": "train",
   "lang": "ru",
   "domain": "geology",
   "nodes": 45,
   "claims": 199,
   "tasks": 38,
   "loops": 11,
   "units": 178,
   "covered": 178,
   "scan": 44
  },
  {
   "id": "basniev",
   "title": "Басниев и др. (2005), гл. XXIII и гл. XXIV §1",
   "set": "train",
   "lang": "ru",
   "domain": "geology",
   "nodes": 48,
   "claims": 181,
   "tasks": 37,
   "loops": 19,
   "units": 357,
   "covered": 357,
   "scan": 51
  },
  {
   "id": "kuznetsov",
   "title": "Кузнецов (2012), гл. 10 §10.1–10.4",
   "set": "train",
   "lang": "ru",
   "domain": "geology",
   "nodes": 41,
   "claims": 183,
   "tasks": 37,
   "loops": 26,
   "units": 121,
   "covered": 121,
   "scan": 28
  }
 ],
 "test": [],
 "control": {
  "targets": 40,
  "errors": 21,
  "found": 19,
  "false": 0,
  "weighted": 90
 },
 "videos": [
  {
   "id": "basniev_response",
   "format": "long",
   "sec": 115.5,
   "check": {
    "voice": "onwK4e9ZLuTAKqWW03F9 (elevenlabs, облако, наружу уходит только текст сценария)",
    "fallback_voice": "ru_RU-dmitri-medium (piper)",
    "wpm": 117.8,
    "lufs": -16.2,
    "sync_max_s": 0.01,
    "sync_note": "по меткам слов: от начала слота фразы до её первого слова и от последнего звука до конца слота",
    "asr_wer": 0.063,
    "asr_note": "faster-whisper small, локально; слов 206, расхождений 13; синхрон по услышанным словам, фраз 17 из 18",
    "asr_errors": [
     "скважину → скважин",
     "пустили → упустили",
     "соседняя → соседнее",
     "двухстах → двухстох",
     "давления → давление",
     "одной → один",
     "десятой → десять",
     "пяти → пять",
     "прогиб → праги",
     "расходится → просходятся",
     "свойства → свойство",
     "пьезопроводность → пизопроводность",
     "свойства → свойство"
    ],
    "asr_terms_lost": [],
    "asr_sync_s": 0.35,
    "check_by_ear": [
     "пьезопроводности",
     "фильтруется",
     "перераспределения",
     "однофазная",
     "насыщения",
     "прогиб"
    ]
   },
   "prediction": "Соседняя скважина в 200 м отзовётся через секунды, минуты или часы?"
  },
  {
   "id": "latyshova_signs",
   "format": "short",
   "sec": 63.6,
   "check": {
    "voice": "onwK4e9ZLuTAKqWW03F9 (elevenlabs, облако, наружу уходит только текст сценария)",
    "fallback_voice": "ru_RU-dmitri-medium (piper)",
    "wpm": 131.3,
    "lufs": -16.1,
    "sync_max_s": 0.01,
    "sync_note": "по меткам слов: от начала слота фразы до её первого слова и от последнего звука до конца слота",
    "asr_wer": 0.024,
    "asr_note": "faster-whisper small, локально; слов 123, расхождений 3; синхрон по услышанным словам, фраз 11 из 12",
    "asr_errors": [
     "излучение → излучения",
     "у → —",
     "песчаника → упещанника"
    ],
    "asr_terms_lost": [],
    "asr_sync_s": 0.9,
    "check_by_ear": [
     "сопротивление",
     "нейтронные",
     "гамма-излучение",
     "песчаник",
     "известняк"
    ]
   },
   "prediction": "Если в песчанике вместо солёной воды нефть, станет ли сопротивление максимальным?"
  }
 ],
 "loops": [
  "kuznetsov.structural_traps",
  "latyshova.water_loss",
  "basniev.psss_radial_front",
  "kuznetsov.karachaganak_zones",
  "latyshova.owc_transition",
  "kuznetsov.secondary_porosity",
  "basniev.piezometric_curves",
  "kuznetsov.seal_formation",
  "latyshova.borehole_wall",
  "kuznetsov.group_atoll",
  "basniev.flow_profile",
  "kuznetsov.reef_deposits"
 ]
};
