/**
 * TypeScript declaration for CSS Module imports
 *
 * This tells TypeScript that any `.module.css` file imports
 * return an object with string keys (class names) mapping to string values
 * (the actual CSS class names after processing).
 */

declare module '*.module.css' {
  const classes: { [key: string]: string };
  export default classes;
}
