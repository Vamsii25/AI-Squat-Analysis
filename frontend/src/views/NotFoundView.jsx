import { Link } from 'react-router-dom'

export default function NotFoundView() {
  return (
    <div className="container-narrow not-found">
      <p className="eyebrow">404</p>
      <h1>Nothing at this bar height.</h1>
      <p>The page you're looking for doesn't exist.</p>
      <Link to="/" className="btn-primary">Back to home</Link>
    </div>
  )
}
