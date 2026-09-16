export const PASSWORD_RULES = [
  { key: "length", label: "At least 8 characters", test: (value) => value.length >= 8 },
  { key: "uppercase", label: "One uppercase letter", test: (value) => /[A-Z]/.test(value) },
  { key: "lowercase", label: "One lowercase letter", test: (value) => /[a-z]/.test(value) },
  { key: "number", label: "One number", test: (value) => /\d/.test(value) },
  { key: "symbol", label: "One symbol", test: (value) => /[^A-Za-z0-9]/.test(value) },
];

export function passwordMeetsPolicy(value) {
  return PASSWORD_RULES.every((rule) => rule.test(value));
}

export function getPasswordScore(value = "") {
  if (!value) return 0;
  return PASSWORD_RULES.filter((rule) => rule.test(value)).length;
}

export function getPasswordStrength(value = "") {
  if (!value) {
    return { score: 0, percent: 0, label: "", status: "empty", isComplete: false };
  }

  const passedCount = getPasswordScore(value);
  const isComplete = passedCount === PASSWORD_RULES.length;

  if (isComplete) {
    return {
      score: 3,
      percent: 100,
      label: "Strong • All requirements met",
      status: "strong",
      isComplete: true,
    };
  }

  if (passedCount >= 3) {
    return {
      score: 2,
      percent: 65,
      label: "Good password",
      status: "medium",
      isComplete: false,
    };
  }

  return {
    score: 1,
    percent: 30,
    label: "Weak password",
    status: "weak",
    isComplete: false,
  };
}
