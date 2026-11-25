import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';

export default function HomePage() {
  return (
    <main className="shell min-h-screen bg-cine-paper text-cine-ink">
      <nav className="topbar" aria-label="Main navigation">
        <Link className="brand" href="/" aria-label="CineSense home"><span className="brand-mark">C</span>CineSense</Link>
        <div className="nav-links"><a href="#discover">Discover</a><a href="#how-it-works">How it works</a></div>
        <a className="nav-action" href="#discover">Start exploring <span aria-hidden="true"><ArrowUpRight size={15} /></span></a>
      </nav>

      <section className="hero" id="discover">
        <div className="hero-copy">
          <p className="eyebrow"><span className="status-dot" /> YOUR NEXT FAVORITE IS OUT THERE</p>
          <h1>Describe the<br />feeling.<br /><em>Discover the</em><br /><em>film.</em></h1>
          <p className="intro">Tell us what you’re in the mood for. We’ll find the film that feels just right.</p>
          <form className="prompt" aria-label="CineSense discovery preview">
            <label className="sr-only" htmlFor="mood">Describe what you want to watch</label>
            <input id="mood" name="mood" placeholder="A clever mystery for a rainy night…" disabled aria-describedby="prompt-hint" />
            <button type="submit" aria-label="Discovery is not available yet" disabled><ArrowUpRight size={20} aria-hidden="true" /></button>
          </form>
          <p className="prompt-hint" id="prompt-hint">Search will be enabled when the catalog and discovery pipeline are connected.</p>
          <div className="quick-picks"><span>EXAMPLE MOODS</span><span className="suggestion">Something uplifting</span><span className="suggestion">A mind-bender</span><span className="suggestion">A cozy classic</span></div>
        </div>
        <div className="hero-art" role="img" aria-label="Abstract cinematic artwork">
          <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
          <div className="art-sun" /><div className="art-caption"><span>01 / 04</span><span>THE FEELING FINDER</span></div>
          <div className="art-title">Stories<br />that stay.</div>
        </div>
      </section>

      <section className="how" id="how-it-works"><div><p className="eyebrow">A BETTER WAY TO CHOOSE</p><h2>Start with a feeling.</h2></div><p>Great recommendations begin with you. CineSense turns the way you feel into a thoughtful shortlist, so choosing your next watch feels effortless.</p></section>
      <footer><Link className="brand" href="/"><span className="brand-mark">C</span>CineSense</Link><span>Made for the love of a good story.</span><span>© 2026 CineSense</span><small>This product uses the <a href="https://www.themoviedb.org/" target="_blank" rel="noreferrer">TMDB API</a> but is not endorsed or certified by TMDB.</small></footer>
    </main>
  );
}
