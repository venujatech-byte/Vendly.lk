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
