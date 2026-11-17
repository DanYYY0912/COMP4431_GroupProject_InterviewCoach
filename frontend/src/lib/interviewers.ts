export const interviewerIds = ['jamie'] as const;
export type InterviewerId = (typeof interviewerIds)[number];
export const interviewers: ReadonlyArray<{ id: InterviewerId; name: string; src: string }> = [
  { id: 'jamie', name: 'Jamie', src: '/interviewers/jamie.png' },
];
const preferenceKey = 'voxprep.interviewer';

export function getInterviewer(id: string | null | undefined) {
  return interviewers.find((interviewer) => interviewer.id === id) || interviewers[0];
}
export function readInterviewerPreference(): InterviewerId {
  try {
    return getInterviewer(localStorage.getItem(preferenceKey)).id;
  } catch {
    return 'jamie';
  }
}
export function saveInterviewerPreference(id: InterviewerId) {
  try {
    localStorage.setItem(preferenceKey, id);
  } catch {
    // Browser storage is optional; the selected face can still be saved with the session.
  }
}
