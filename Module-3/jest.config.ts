import type { Config } from "jest";

const config: Config = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  roots: ["<rootDir>/src"],
  testMatch: ["**/__tests__/**/*.test.{ts,tsx}"],
  moduleNameMapper: {
    "\\.module\\.css$": "identity-obj-proxy",
    "\\.css$": "identity-obj-proxy",
  },
  transform: {
    "^.+\\.tsx?$": "ts-jest",
  },
};

export default config;
