import { Link } from "react-router-dom";
import { StatusView } from "../components/StatusView.tsx";

export function NotFoundPage() {
  return (
    <StatusView
      title="Page not found"
      detail="The route does not exist in this frontend workspace yet."
      action={
        <Link className="button button-primary" to="/">
          Return home
        </Link>
      }
    />
  );
}
