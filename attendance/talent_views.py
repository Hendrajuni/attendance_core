from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Employee, PersonalityTest, TraitDictionary, PersonalityIndicator, WorkLocation
from .services.psychology_engine import process_psychology_excel, calculate_dynamic_form, calculate_role_synergy

@login_required
def talent_dashboard(request):
    """
    Dashboard Modul Psikotes (MPTT Tree View)
    """
    from django.db.models import Count, Q
    all_locations = WorkLocation.objects.all()
    locations = all_locations
    
    # Removed Import Excel logic, moved to talent_manual_form

    context = {
        'page_title': 'Talent Development Dashboard',
        'locations': locations,
    }
    return render(request, 'talent/talent_dashboard.html', context)


@login_required
def talent_location_dashboard_htmx(request, location_id=None):
    """
    HTMX Endpoint: Mengambil dan merender statistik psikotes berdasarkan lokasi.
    Jika location_id None, ambil statistik global.
    """
    tests = PersonalityTest.objects.select_related('employee', 'employee__department', 'employee__home_base')
    location = None
    
    if location_id:
        location = get_object_or_404(WorkLocation, id=location_id)
        # Ambil karyawan di lokasi ini dan turunannya
        descendant_locations = location.get_descendants(include_self=True)
        tests = tests.filter(employee__home_base__in=descendant_locations)
    
    tests = tests.order_by('-test_date')
    
    # Search
    search_q = request.GET.get('search', '')
    if search_q:
        tests = tests.filter(employee__full_name__icontains=search_q)
    
    # Hitung Tipe Karakter Dominan
    traits_count = {
        'Sanguinis': tests.filter(primary_trait__icontains='Sanguinis').count(),
        'Melankolis': tests.filter(primary_trait__icontains='Melankolis').count(),
        'Koleris': tests.filter(primary_trait__icontains='Koleris').count(),
        'Plegmatis': tests.filter(primary_trait__icontains='Plegmatis').count(),
    }
    
    # Hitung Tingkat Sinergi (Synergy Risk Board)
    synergy_count = {
        'sangat_sinergi': tests.filter(synergy_score__gte=80).count(),
        'pendampingan': tests.filter(synergy_score__gte=50, synergy_score__lt=80).count(),
        'beresiko': tests.filter(synergy_score__lt=50).count(),
    }

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(tests, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'location': location,
        'tests': page_obj, 
        'total_tests': tests.count(),
        'traits_count': traits_count,
        'synergy_count': synergy_count,
        'search_q': search_q,
    }
    return render(request, 'talent/partials/_location_dashboard.html', context)


@login_required
def talent_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    
    # Riwayat seluruh tes untuk karyawan ini
    test_history = PersonalityTest.objects.filter(employee=employee).order_by('-test_date')
    
    if not test_history.exists():
        messages.error(request, "Belum ada riwayat tes psikotes untuk karyawan ini.")
        return redirect('attendance:talent_manual_form')
        
    latest_test = test_history.first()
    
    # Hitung Konsensus Gabungan
    count = test_history.count()
    t_s = sum(t.sanguine_score for t in test_history) / count
    t_m = sum(t.melancholic_score for t in test_history) / count
    t_k = sum(t.choleric_score for t in test_history) / count
    t_p = sum(t.phlegmatic_score for t in test_history) / count
    t_jj = sum(t.honesty_score for t in test_history) / count
    t_tj = sum(t.responsibility_score for t in test_history) / count
    total = t_s + t_m + t_k + t_p

    # Dominant trait is based on averages
    averages = {'Sanguinis': t_s, 'Melankolis': t_m, 'Koleris': t_k, 'Plegmatis': t_p}
    dominant_trait = max(averages, key=averages.get)
    dictionary = TraitDictionary.objects.filter(trait_name__icontains=dominant_trait).first()
    
    # Perbarui object latest_test untuk UI yang masih memakai field model
    latest_test.primary_trait = dominant_trait
    latest_test.honesty_score = int(t_jj)
    latest_test.responsibility_score = int(t_tj)
    
    compositions = {
        'sanguine': (t_s / total * 100) if total > 0 else 0,
        'melancholic': (t_m / total * 100) if total > 0 else 0,
        'choleric': (t_k / total * 100) if total > 0 else 0,
        'phlegmatic': (t_p / total * 100) if total > 0 else 0,
    }
    
    context = {
        'talent': latest_test, # Kita pass test terakhir, tapi primary trait-nya disesuaikan dgn consensus
        'dictionary': dictionary,
        'test_history': test_history,
        'compositions': compositions,
        'total_evaluators': count,
        'title': f"Profil Talent: {employee.full_name}"
    }
    return render(request, 'talent/talent_detail.html', context)

@login_required
def talent_manual_form(request):
    """
    Form Web Manual untuk HR menginput data hasil psikotes satu per satu secara langsung (tanpa Excel)
    """
    if request.method == 'POST':
        # --- LOGIK KHUSUS IMPORT EXCEL ---
        if 'excel_file' in request.FILES:
            success, errors = process_psychology_excel(request.FILES['excel_file'], request.user)
            if success > 0:
                messages.success(request, f"Berhasil mengimport {success} data hasil psikotes.")
            if errors:
                for err in errors[:5]:
                    messages.warning(request, err)
            return redirect('attendance:talent_manual_form')

        action = request.POST.get('action')
        
        # --- LOGIK KHUSUS PENAMBAHAN KANDIDAT REKRUTMEN ---
        if action == 'add_candidate':
            candidate_name = request.POST.get('candidate_name')
            candidate_phone = request.POST.get('candidate_phone', '')
            candidate_position = request.POST.get('candidate_position', 'Kandidat Rekrutmen')
            candidate_dob = request.POST.get('candidate_dob')
            candidate_blood = request.POST.get('candidate_blood')
            
            if candidate_name:
                import uuid
                # Buat temporary NIK untuk kandidat
                temp_nik = f"REC-{uuid.uuid4().hex[:6].upper()}"
                
                # Create draft employee
                new_candidate = Employee.objects.create(
                    nik=temp_nik,
                    full_name=candidate_name,
                    phone_number=candidate_phone,
                    position=candidate_position,
                    date_of_birth=candidate_dob if candidate_dob else None,
                    blood_type=candidate_blood if candidate_blood else None,
                    is_verified=False, # MARK AS DRAFT
                    employee_type='KARYAWAN'
                )
                messages.success(request, f"Kandidat {candidate_name} berhasil diregistrasi sementara.")
                return redirect('attendance:talent_manual_form')
                
        # --- LOGIKA UTAMA SIMPAN PSIKOTES ---
        nik_or_id = request.POST.get('employee_id')
        employee = Employee.objects.filter(id=nik_or_id).first()
        
        if not employee:
            messages.error(request, "Karyawan tidak ditemukan.")
            return redirect('attendance:talent_manual_form')
            
        try:
            checked_indicators = request.POST.getlist('indicators')
            jujur_val = float(request.POST.get('jujur_score', 0))
            tggjawab_val = float(request.POST.get('tggjawab_score', 0))
            
            manual_scores = {
                'Sanguinis': request.POST.get('manual_sanguine', 0) or 0,
                'Melankolis': request.POST.get('manual_melancholic', 0) or 0,
                'Koleris': request.POST.get('manual_choleric', 0) or 0,
                'Plegmatis': request.POST.get('manual_phlegmatic', 0) or 0,
            }
            
            # Kalkulasi dari checklist
            evaluasi = calculate_dynamic_form(checked_indicators, jujur_val, tggjawab_val, manual_scores)
            synergy = calculate_role_synergy(evaluasi['primary_trait'], employee.position)
            
            PersonalityTest.objects.update_or_create(
                employee=employee,
                evaluator=request.user,
                test_date=timezone.now().date(),
                defaults={
                    'sanguine_score': evaluasi['scores']['Sanguinis'],
                    'melancholic_score': evaluasi['scores']['Melankolis'],
                    'choleric_score': evaluasi['scores']['Koleris'],
                    'phlegmatic_score': evaluasi['scores']['Plegmatis'],
                    'honesty_score': evaluasi['honesty_score'],
                    'responsibility_score': evaluasi['responsibility_score'],
                    'sanguine_maturity': evaluasi['maturities']['Sanguinis'],
                    'melancholic_maturity': evaluasi['maturities']['Melankolis'],
                    'choleric_maturity': evaluasi['maturities']['Koleris'],
                    'phlegmatic_maturity': evaluasi['maturities']['Plegmatis'],
                    'primary_trait': evaluasi['primary_trait'],
                    'secondary_trait': evaluasi['secondary_trait'],
                    'synergy_score': synergy,
                    'consultant_notes': request.POST.get('catatan', ''),
                    'raw_responses': evaluasi['raw_responses'],
                }
            )
            messages.success(request, f"Data Evaluasi {employee.full_name} berhasil disimpan.")
            return redirect('attendance:talent_manual_form')
            
        except Exception as e:
            messages.error(request, f"Error menyimpan data: {str(e)}")

    # Get non-evaluated employees
    employees = Employee.objects.filter(is_active=True).order_by('full_name')
    
    # Ambil semua history test untuk table
    test_results = PersonalityTest.objects.select_related('employee', 'evaluator').all().order_by('employee__full_name', '-test_date')
    
    # Filter Date
    filter_year = request.GET.get('year')
    filter_month = request.GET.get('month')
    
    active_tab = request.GET.get('active_tab', 'karyawan')
    
    if filter_year:
        test_results = test_results.filter(test_date__year=filter_year)
    if filter_month:
        test_results = test_results.filter(test_date__month=filter_month)
        
    counts = {
        'karyawan': test_results.filter(employee__is_verified=True).count(),
        'rekrutmen': test_results.filter(employee__is_verified=False).count(),
    }
        
    if active_tab == 'rekrutmen':
        test_results = test_results.filter(employee__is_verified=False)
    else:
        test_results = test_results.filter(employee__is_verified=True)
    
    # Ambil semua soal/indikator yang sudah diregister HRD di backend admin
    indicators = PersonalityIndicator.objects.filter(is_active=True).order_by('kind', 'indicator_text')
    
    # Kelompokkan berdasarkan kategori
    dict_indicators = {'S': [], 'M': [], 'K': [], 'P': []}
    for ind in indicators:
        if ind.category in dict_indicators:
            dict_indicators[ind.category].append(ind)
    locations = WorkLocation.objects.all().order_by('name')
    
    context = {
        'employees': employees,
        'test_results': test_results,
        'active_tab': active_tab,
        'counts': counts,
        'locations': locations,
        'dict_indicators': dict_indicators,
        'current_year': filter_year or timezone.now().year,
        'current_month': filter_month or timezone.now().month,
        'title': 'Inteligensi Cerdas (Test Center)'
    }
    return render(request, 'talent/talent_manual_form.html', context)


@login_required
def talent_print_report(request):
    """ View khusus untuk mencetak report test psikotes hasil filter (no sidebar/navbar) """
    if not (request.user.groups.filter(name__in=['HRD', 'Manager']).exists() or request.user.is_superuser):
        messages.error(request, "Anda tidak memiliki akses (Cetak Laporan).")
        return redirect('portal:dashboard')

    # Ambil history test untuk table (hanya yang karyawan)
    test_results = PersonalityTest.objects.select_related('employee', 'evaluator').all().order_by('employee__full_name', '-test_date')
    
    # Filter Date
    filter_year = request.GET.get('year')
    filter_month = request.GET.get('month')
    
    if filter_year:
        test_results = test_results.filter(test_date__year=filter_year)
    if filter_month:
        test_results = test_results.filter(test_date__month=filter_month)

    # Hitung Tipe Karakter Dominan khusus yang sudah difilter
    traits_count = {
        'Sanguinis': test_results.filter(primary_trait__icontains='Sanguinis').count(),
        'Melankolis': test_results.filter(primary_trait__icontains='Melankolis').count(),
        'Koleris': test_results.filter(primary_trait__icontains='Koleris').count(),
        'Plegmatis': test_results.filter(primary_trait__icontains='Plegmatis').count(),
    }
    
    # Text helper untuk judul bulan/tahun di kertas
    import datetime
    month_name = datetime.date(1900, int(filter_month), 1).strftime('%B') if filter_month else 'Semua Bulan'
    year_name = filter_year if filter_year else 'Semua Tahun'

    context = {
        'test_results': test_results,
        'traits_count': traits_count,
        'filter_month': filter_month,
        'filter_year': filter_year,
        'month_name': month_name,
        'year_name': year_name,
        'now': timezone.now()
    }
    
    return render(request, 'talent/talent_print_report.html', context)
