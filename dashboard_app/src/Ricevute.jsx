import RicevuteClienti from './RicevuteClienti';
import RicevuteValoriBollati from './RicevuteValoriBollati';

export default function Ricevute({ section = 'clienti' }) {
  if (section === 'valori-bollati') {
    return <RicevuteValoriBollati />;
  }
  return <RicevuteClienti />;
}
