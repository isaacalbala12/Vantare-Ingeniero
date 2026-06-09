/** Pure helpers for PTT voice → text → pilot_question (unit-tested). */

export const PTT_MIN_QUESTION_CHARS = 2;
export const PTT_MIN_WAV_BYTES = 512;

export const PTT_EMPTY_MESSAGE = "No te oí. Mantén PTT y repite la pregunta.";

export function mergePttTranscripts(speechRecognitionText: string, backendTranscript: string): string {
  const sr = speechRecognitionText.trim();
  const backend = backendTranscript.trim();
  if (!backend) return sr;
  if (!sr) return backend;
  const srWords = sr.split(/\s+/).filter(Boolean).length;
  const backendWords = backend.split(/\s+/).filter(Boolean).length;
  return backendWords >= srWords ? backend : sr;
}

export function shouldTranscribeWav(wavSize: number): boolean {
  return wavSize >= PTT_MIN_WAV_BYTES;
}

export type PttResolution =
  | { status: "ready"; question: string }
  | { status: "empty"; message: string };

export function resolvePttQuestion(raw: string): PttResolution {
  const question = raw.trim();
  if (question.length < PTT_MIN_QUESTION_CHARS) {
    return { status: "empty", message: PTT_EMPTY_MESSAGE };
  }
  return { status: "ready", question };
}

export async function transcribePttWav(wavBlob: Blob, baseUrl: string): Promise<string> {
  if (!shouldTranscribeWav(wavBlob.size)) return "";
  const formData = new FormData();
  formData.append("audio", wavBlob, "ptt_recording.wav");
  try {
    const res = await fetch(`${baseUrl}/transcribe`, { method: "POST", body: formData });
    if (!res.ok) return "";
    const data = (await res.json()) as { text?: string };
    return (data.text || "").trim();
  } catch {
    return "";
  }
}

export async function buildPttQuestionText(
  speechRecognitionText: string,
  wavBlob: Blob | null,
  baseUrl: string,
): Promise<string> {
  let questionText = speechRecognitionText.trim();
  if (wavBlob && wavBlob.size > 0) {
    const backendText = await transcribePttWav(wavBlob, baseUrl);
    questionText = mergePttTranscripts(questionText, backendText);
  }
  return questionText;
}
