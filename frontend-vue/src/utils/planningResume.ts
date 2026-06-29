const PLANNING_RESUME_MARKER = '<<RESUME_ANSWERS>>'
const RESUME_JSON_TYPE = 'planning_resume'

export interface PlanningResumePayload {
  questionSetId?: string
  answers: Record<string, string>
}

export interface PlanningDisplayAnswer {
  question: string
  answer: string
}

export function buildPlanningResumeJson(payload: PlanningResumePayload): string {
  return JSON.stringify({
    type: RESUME_JSON_TYPE,
    questionSetId: payload.questionSetId || '',
    answers: payload.answers,
  })
}

export function isPlanningResumeJson(message: string): boolean {
  return message.startsWith('{') && message.includes(`"${RESUME_JSON_TYPE}"`)
}

export function buildPlanningResumePrompt(payload: PlanningResumePayload): string {
  const body: PlanningResumePayload = payload.questionSetId
    ? { questionSetId: payload.questionSetId, answers: payload.answers }
    : { answers: payload.answers }
  return `${PLANNING_RESUME_MARKER}${JSON.stringify(body)}${PLANNING_RESUME_MARKER}`
}

export function buildPlanningResumeDisplay(items: PlanningDisplayAnswer[]): string {
  if (items.length === 0) {
    return '跳过补充需求，请继续生成。'
  }
  const readableAnswers = items.map((item) => `${item.question}：答：${item.answer}`)
  return `需求补充：${readableAnswers.join('；')}\n\n请继续生成。`
}
