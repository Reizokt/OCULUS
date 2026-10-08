import { useNavigate } from 'react-router-dom';
import { SectorMap } from '../blocks';

export default function Sectors() {
  const navigate = useNavigate();
  return (
    <div className="mt-grid">
      <div className="mt-span-12"><SectorMap size="full" onSelect={(symbol) => navigate(`/company/${symbol}`)} /></div>
    </div>
  );
}
