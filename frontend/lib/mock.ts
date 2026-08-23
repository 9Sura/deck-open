// Mock generation output for the UI (Pass 2). Shapes mirror the real backend
// output so the Pass 3 swap to a live API is drop-in.
// TODO(pass-3): replace these with POST /api/generate-* responses.

export interface MockQuestion {
  question: string;
  options: { A: string; B: string; C: string; D: string };
  answer: "A" | "B" | "C" | "D";
  explanation: string;
  instructionalArea: string;
  performanceIndicator: string;
}

export const MOCK_QUESTIONS: MockQuestion[] = [
  {
    question:
      "A customer is unhappy with a product they purchased. The associate should first ask for details about the problem, then explain how the company will help. What does this show about communication?",
    options: {
      A: "It means telling others what to do.",
      B: "It means listening carefully to others' concerns.",
      C: "It means providing a solution immediately.",
      D: "It means giving orders to resolve conflict.",
    },
    answer: "B",
    explanation:
      "Effective communication starts with listening. The associate must understand the issue before responding with empathy and a solution — offering a fix or giving directions comes later.",
    instructionalArea: "Customer Relations",
    performanceIndicator: "Reinforce service orientation through communication",
  },
  {
    question:
      "A manager is deciding whether to promote a recently hired employee. Which characteristic is MOST relevant to the decision?",
    options: {
      A: "The employee's ability to work well in a team.",
      B: "The employee's willingness to take risks.",
      C: "The employee's level of education.",
      D: "The employee's tenure with the company.",
    },
    answer: "A",
    explanation:
      "Ability to collaborate is the strongest predictor of success in most roles. Tenure and risk tolerance matter less than demonstrated teamwork for a promotion decision.",
    instructionalArea: "Emotional Intelligence",
    performanceIndicator: "Explain the concept of leadership",
  },
  {
    question: "What is the primary function of economic goods?",
    options: {
      A: "To provide personal satisfaction only.",
      B: "To meet the needs of governments.",
      C: "To produce income for individuals and businesses.",
      D: "To promote social welfare programs.",
    },
    answer: "C",
    explanation:
      "Economic goods have value and are produced and sold to generate income. Personal satisfaction is a byproduct, not the primary economic function.",
    instructionalArea: "Economics",
    performanceIndicator: "Distinguish between economic goods and services",
  },
  {
    question:
      "A firm wants to compare this year's net profit to last year's. Which financial statement provides this information?",
    options: {
      A: "The balance sheet.",
      B: "The income statement.",
      C: "The cash flow statement.",
      D: "The statement of retained earnings.",
    },
    answer: "B",
    explanation:
      "The income statement reports revenues and expenses over a period, ending in net profit — the figure needed to compare year over year. The balance sheet is a point-in-time snapshot.",
    instructionalArea: "Financial Analysis",
    performanceIndicator: "Describe the nature of income statements",
  },
  {
    question:
      "A company is choosing a channel to distribute a new product to a wide, national audience quickly. Which channel is MOST appropriate?",
    options: {
      A: "A single exclusive retailer.",
      B: "Direct-to-consumer only.",
      C: "Intensive distribution through many outlets.",
      D: "A limited pop-up presence.",
    },
    answer: "C",
    explanation:
      "Intensive distribution places a product in as many outlets as possible — the right fit for wide, fast national reach. Exclusive and limited channels intentionally restrict availability.",
    instructionalArea: "Channel Management",
    performanceIndicator: "Explain the nature of channels of distribution",
  },
];

// MOCK_ROLEPLAY / MockRoleplay lived here to feed the retired /roleplay generator
// draft. Roleplays now have a real contract and real committed data
// (lib/roleplay/types.ts + public/roleplays/), so there is nothing left to mock.
