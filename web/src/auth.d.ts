export {};
declare global {
  interface Window {
    mithuAuth?: {
      getIdentityAssertion: () => Promise<string>;
    };
  }
}