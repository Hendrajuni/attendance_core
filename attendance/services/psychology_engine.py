import pandas as pd
from typing import Dict, Any, Tuple
from django.utils import timezone
from attendance.models import Employee, PersonalityTest, RoleSynergyMaster

def clean_excel_string(val):
    """Helper for cleaning nan/float string inputs from pandas"""
    if pd.isna(val):
        return ""
    return str(val).strip()

def process_psychology_excel(file, evaluator_user=None) -> Tuple[int, list]:
    """
    Mengambil file Excel yang diupload, memparsingnya (K, S, M, P, JJ, TJ),
    dan menghitung evaluasi lalu dimasukkan ke database.
    """
    df = pd.read_excel(file)
    success_count = 0
    errors = []

    # Normalisasi nama kolom (hilangkan spasi berlebih & ubah ke UPPER)
    df.rename(columns=lambda x: str(x).strip().upper(), inplace=True)

    required_cols = ['K', 'S', 'M', 'P']
    if not all(col in df.columns for col in required_cols) or ('NAMA' not in df.columns and 'NIK' not in df.columns):
        return 0, [f"Format Error: Kolom Excel wajib berisi (K, S, M, P) beserta (Nama atau NIK)."]

    for index, row in df.iterrows():
        try:
            nama = str(row.get('NAMA', '')).strip()
            nik = str(row.get('NIK', '')).strip()
            
            if (pd.isna(nama) or not nama) and (pd.isna(nik) or not nik):
                continue
                
            employee = None
            if nik and not pd.isna(nik):
                from django.db.models import Q
                employee = Employee.objects.filter(Q(company_nik=nik) | Q(nik=nik)).first()
            
            if not employee and nama and not pd.isna(nama):
                employee = Employee.objects.filter(full_name__icontains=nama).first()
                
            if not employee:
                errors.append(f"Baris {index + 2}: Karyawan dengan Nama '{nama}' atau NIK '{nik}' tidak ditemukan di database.")
                continue

            # Menangkap Data Inti
            scores = {
                'Sanguinis': float(row.get('S', 0) or 0),
                'Melankolis': float(row.get('M', 0) or 0),
                'Koleris': float(row.get('K', 0) or 0),
                'Plegmatis': float(row.get('P', 0) or 0),
            }
            
            if sum(scores.values()) == 0:
                continue
            
            jj_score = float(row.get('JJ', 0) or 0)
            tj_score = float(row.get('TJ', 0) or 0)
            consultant_notes = clean_excel_string(row.get('KET', ''))

            # 3. Urutkan berdasarkan Skor Tertinggi
            sorted_traits = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            primary_trait = sorted_traits[0][0]
            secondary_trait = sorted_traits[1][0] if sorted_traits[1][1] > 0 else ""
            
            # Evaluasi Sinergi
            synergy = calculate_role_synergy(primary_trait, employee.position)
            
            # Simpan ke Database (Update jika ada, Create jika baru)
            PersonalityTest.objects.update_or_create(
                employee=employee,
                evaluator=evaluator_user,
                test_date=timezone.now().date(),
                defaults={
                    'sanguine_score': scores['Sanguinis'],
                    'melancholic_score': scores['Melankolis'],
                    'choleric_score': scores['Koleris'],
                    'phlegmatic_score': scores['Plegmatis'],
                    'honesty_score': jj_score,
                    'responsibility_score': tj_score,
                    'sanguine_maturity': 0, # Dari excel agregat tidak ada info detail
                    'melancholic_maturity': 0,
                    'choleric_maturity': 0,
                    'phlegmatic_maturity': 0,
                    'primary_trait': primary_trait,
                    'secondary_trait': secondary_trait,
                    'synergy_score': synergy,
                    'consultant_notes': consultant_notes,
                    'input_source': 'EXCEL',
                }
            )
            success_count += 1
            
        except Exception as e:
            errors.append(f"Baris {index + 2}: Terjadi kesalahan internal ({str(e)})")

    return success_count, errors


def calculate_dynamic_form(checked_indicators_ids: list, jujur_val: float, tggjawab_val: float, manual_scores: dict = None) -> Dict[str, Any]:
    """
    Logika Form Web Checklist Cerdas:
    Menghitung total skor dan kematangan berdasarkan referensi `PersonalityIndicator`.
    Juga memprioritaskan nilai override (manual input).
    """
    from attendance.models import PersonalityIndicator
    
    indicators = PersonalityIndicator.objects.filter(id__in=checked_indicators_ids)
    
    raw_scores = {
        'S': {'pos': 0, 'neg': 0},
        'M': {'pos': 0, 'neg': 0},
        'K': {'pos': 0, 'neg': 0},
        'P': {'pos': 0, 'neg': 0},
    }
    
    for ind in indicators:
        if ind.category in raw_scores:
            if ind.kind == 'POS':
                raw_scores[ind.category]['pos'] += ind.weight
            else:
                raw_scores[ind.category]['neg'] += ind.weight
                
    # 1. Total (Kekuatan Pendorong)
    scores = {
        'Sanguinis': raw_scores['S']['pos'] + raw_scores['S']['neg'],
        'Melankolis': raw_scores['M']['pos'] + raw_scores['M']['neg'],
        'Koleris': raw_scores['K']['pos'] + raw_scores['K']['neg'],
        'Plegmatis': raw_scores['P']['pos'] + raw_scores['P']['neg'],
    }
    
    # 1b. Override jika ada nilai tembak manual (mewakili total valid)
    if manual_scores:
        if manual_scores.get('Sanguinis') and float(manual_scores['Sanguinis']) > 0:
            scores['Sanguinis'] = float(manual_scores['Sanguinis'])
            raw_scores['S']['pos'] = scores['Sanguinis'] # Asumsi pos murni jika override
        if manual_scores.get('Melankolis') and float(manual_scores['Melankolis']) > 0:
            scores['Melankolis'] = float(manual_scores['Melankolis'])
            raw_scores['M']['pos'] = scores['Melankolis']
        if manual_scores.get('Koleris') and float(manual_scores['Koleris']) > 0:
            scores['Koleris'] = float(manual_scores['Koleris'])
            raw_scores['K']['pos'] = scores['Koleris']
        if manual_scores.get('Plegmatis') and float(manual_scores['Plegmatis']) > 0:
            scores['Plegmatis'] = float(manual_scores['Plegmatis'])
            raw_scores['P']['pos'] = scores['Plegmatis']
    
    # 2. Maturity Level
    maturities = {
        'Sanguinis': (raw_scores['S']['pos'] / scores['Sanguinis'] * 100) if scores['Sanguinis'] > 0 else 0,
        'Melankolis': (raw_scores['M']['pos'] / scores['Melankolis'] * 100) if scores['Melankolis'] > 0 else 0,
        'Koleris': (raw_scores['K']['pos'] / scores['Koleris'] * 100) if scores['Koleris'] > 0 else 0,
        'Plegmatis': (raw_scores['P']['pos'] / scores['Plegmatis'] * 100) if scores['Plegmatis'] > 0 else 0,
    }
    
    # 3. Urutkan berdasarkan Skor Tertinggi
    sorted_traits = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary_trait = sorted_traits[0][0]
    secondary_trait = sorted_traits[1][0] if sorted_traits[1][1] > 0 else ""
    
    return {
        'scores': scores,
        'maturities': maturities,
        'primary_trait': primary_trait,
        'secondary_trait': secondary_trait,
        'honesty_score': jujur_val,
        'responsibility_score': tggjawab_val,
        'raw_responses': {
            'checked_indicators': [ind.indicator_text for ind in indicators]
        }
    }


def calculate_role_synergy(primary_trait: str, position_name: str) -> float:
    """
    Kalkulasi Kedekatan Karakter Utama dengan kebutuhan Jabatan
    """
    if not position_name:
        return 50.0  # Jika jabatan tidak terdefinisi secara baik di system
        
    master = RoleSynergyMaster.objects.filter(position_name__icontains=position_name).first()
    
    if not master:
        # Default middle ground if no mapping exists for this role
        return 65.0
        
    ideal_list = [t.strip().lower() for t in master.ideal_primary_traits.split(',')]
    warning_list = [t.strip().lower() for t in master.warning_primary_traits.split(',')]
    
    pt_lower = primary_trait.lower()
    
    synergy = 70.0 # Default / Netral
    
    if pt_lower in ideal_list:
        synergy = 95.0
    elif pt_lower in warning_list:
        synergy = 40.0
        
    return synergy
