#! /usr/bin/env python3

## import modules
from Bio import Entrez
from Bio.SeqIO import FastaIO 
from tqdm import tqdm
from urllib.error import HTTPError
import time
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq
import subprocess as sp
import os
import shutil
import gzip
from string import digits
import zipfile
import codecs


## functions NCBI
def esearch_fasta(query, database, email):
    Entrez.email = email
    first_handle = Entrez.esearch(db=database, term=query, rettype='fasta')
    first_record = Entrez.read(first_handle)
    first_handle.close()
    count = int(first_record['Count'])
    # now, second round from first
    second_handle = Entrez.esearch(db=database, term=query, retmax=count, rettype='fasta', usehistory = 'y')
    second_record = Entrez.read(second_handle)
    second_handle.close()
    return second_record

def efetch_seqs_from_webenv(web_record, database, email, batch_size, output):
    Entrez.email = email
    id_list = web_record['IdList']
    count = int(web_record['Count'])
    assert(count == len(id_list))
    webenv = web_record['WebEnv']
    query_key = web_record['QueryKey']

    out_handle = open(output, 'w')
    for start in tqdm(range(0, count, batch_size)):
        attempt = 1
        success = False
        while attempt <= 3 and not success:
            attempt += 1
            try:
                fetch_handle = Entrez.efetch(db=database, rettype='fasta',
                                            retstart=start, retmax=batch_size,
                                            webenv=webenv, query_key=query_key)
                success = True
            except HTTPError as err:
                if 500 <= err.code <= 599:
                    print(f"Received error from server {err}")
                    print("Attempt {attempt} of 3")
                    time.sleep(15)
                else:
                    raise
        data = fetch_handle.read()
        fetch_handle.close()
        out_handle.write(data)
    out_handle.close()
    numseq = len(list(SeqIO.parse(output, 'fasta')))

    return numseq

def ncbi_formatting(file):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    header_info = {}
    discarded = []
    for record in SeqIO.parse('CRABS_ncbi_download.fasta', 'fasta'):
        acc = str(record.description.split('.')[0])
        if not any(mistake in acc for mistake in mistakes):
            header_info[acc] = record.description
            record.description = acc
            record.id = record.description
            newfile.append(record)
        else:
            discarded.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(file, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
    discarded_file = file + 'DISCARDED_SEQS.fasta'
    with open(discarded_file, 'w') as fbad:
        for item in discarded_db:
            fbad.write(item)
    header_file = file + '.taxid_table.tsv'
    with open(header_file, 'w') as f_out:
        for k, v in header_info.items():
            f_out.write(k + '\t' + v + '\n')
    numdiscard = len(discarded)
    print(f'found {numdiscard} sequences with incorrect accession format')
    os.remove('CRABS_ncbi_download.fasta')
    numseq = len(newfile)

    return numseq

## functions MitoFish
def mitofish_download(website):
    results = sp.run(['wget', website])
    results = sp.run(['unzip', 'complete_partial_mitogenomes.zip'])
    fasta = 'complete_partial_mitogenomes.fa'
    os.remove('complete_partial_mitogenomes.zip')

    return fasta

def mitofish_format(file_in, file_out):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    header_info = {}
    discarded = []
    for record in SeqIO.parse(file_in, 'fasta'):
        acc = str(record.description.split('|')[1])
        if acc.isdigit():
            acc = str(record.description.split('|')[3])
        if not any(mistake in acc for mistake in mistakes):
            header_info[acc] = record.description
            record.description = acc
            record.id = record.description
            newfile.append(record)
        else:
            discarded.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(file_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
    discarded_file = file_out + 'DISCARDED_SEQS.fasta'
    with open(discarded_file, 'w') as fbad:
        for item in discarded_db:
            fbad.write(item)
    header_file = file_out + '.taxid_table.tsv'
    with open(header_file, 'w') as f_out:
        for k, v in header_info.items():
            f_out.write(k + '\t' + v + '\n')
    numdiscard = len(discarded)
    print(f'found {numdiscard} sequences with incorrect accession format')
    numseq = len(newfile)
    os.remove(file_in)

    return numseq

## functions EMBL
def embl_download(database):
    url = 'ftp://ftp.ebi.ac.uk/pub/databases/embl/release/std/rel_std_' + database
    result = sp.run(['wget', url])
    gfiles = [f for f in os.listdir() if f.startswith('rel_std')]
    ufiles = []
    for gfile in gfiles:
        unzip = gfile[:-3]
        ufiles.append(unzip)
        print(f'unzipping file: {unzip}')
        results = sp.run(['gunzip', gfile])
    
    return ufiles

def embl_fasta_format(dat_format):
    ffiles = []
    for ufile in dat_format:
        ffile = ufile[:-4] + '.fasta'
        ffiles.append(ffile)
        fasta = []
        with open(ufile, 'r') as file:
            print(f'formatting {ufile} to fasta format')
            is_required = False
            for line in file:
                if line.startswith('AC'):
                    part = '>' + line.split('   ')[1].split(';')[0]
                    fasta.append(part)
                elif is_required and line.startswith(' '):
                    remove_digits = str.maketrans('', '', digits)
                    seq = line.replace(' ', '').translate(remove_digits).upper().rstrip('\n')
                    fasta.append(seq)
                else:
                    is_required = 'SQ' in line
        with open(ffile, 'w') as fa:
            print(f'saving {ffile}')
            for element in fasta:
                fa.write('{}\n'.format(element))
    for file in dat_format:
        os.remove(file)
    intermediary_file = 'CRABS_embl_download.fasta'
    print('Combining all EMBL downloaded fasta files...')
    with open(intermediary_file, 'w') as w_file:
        for filen in ffiles:
            with open(filen, 'rU') as o_file:
                seq_records = SeqIO.parse(o_file, 'fasta')
                SeqIO.write(seq_records, w_file, 'fasta')
    for f in ffiles:
        os.remove(f)
    return intermediary_file

def embl_crabs_format(f_in, f_out):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    header_info = {}
    discarded = []
    for record in SeqIO.parse(f_in, 'fasta'):
        acc = str(record.id)
        if not any(mistake in acc for mistake in mistakes):
            header_info[acc] = record.description
            record.description = acc
            record.id = record.description
            newfile.append(record)
        else:
            discarded.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(f_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
    discarded_file = f_out + 'DISCARDED_SEQS.fasta'
    with open(discarded_file, 'w') as fbad:
        for item in discarded_db:
            fbad.write(item)
    header_file = f_out + '.taxid_table.tsv'
    with open(header_file, 'w') as f_out:
        for k, v in header_info.items():
            f_out.write(k + '\t' + v + '\n')
    numdiscard = len(discarded)
    print(f'found {numdiscard} sequences with incorrect accession format')
    numseq = len(newfile)
    os.remove(f_in)

    return numseq

## functions BOLD
def bold_download(entry):
    url = 'http://v3.boldsystems.org/index.php/API_Public/sequence?taxon=' + entry 
    filename = 'CRABS_bold_download.fasta'
    result = sp.run(['wget', url, '-O', filename])
    BLOCKSIZE = 1048576
    with codecs.open(filename, 'r', 'latin1') as sourcefile:
        with codecs.open('mid.fasta', 'w', 'utf-8') as targetfile:
            while True:
                contents = sourcefile.read(BLOCKSIZE)
                if not contents:
                    break
                targetfile.write(contents)
    results = sp.run(['mv', 'mid.fasta', filename])
    num_bold = len(list(SeqIO.parse(filename, 'fasta')))
    
    return num_bold

def bold_format(f_out):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    header_info = {}
    discarded = []
    for record in SeqIO.parse('CRABS_bold_download.fasta', 'fasta'):
        if record.description.split('-')[-1] == 'SUPPRESSED':
            discarded.append(record)
        else:
            if len(record.description.split('|')) == 4:
                acc = str(record.description.split('|')[3].split('.')[0])
                if not any(mistake in acc for mistake in mistakes):
                    header_info[acc] = record.description
                    record.description = acc
                    record.id = record.description
                    newfile.append(record)
                else:
                    discarded.append(record)
            else:
                spec = record.description.split('|')[1]
                acc_crab = 'CRABS:' + spec 
                header_info[acc_crab] = record.description
                record.description = acc_crab
                record.id = record.description
                newfile.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(f_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
    discarded_file = f_out + 'DISCARDED_SEQS.fasta'
    with open(discarded_file, 'w') as fbad:
        for item in discarded_db:
            fbad.write(item)
    header_file = f_out + '.taxid_table.tsv'
    with open(header_file, 'w') as f_out:
        for k, v in header_info.items():
            f_out.write(k + '\t' + v + '\n')
    numdiscard = len(discarded)
    print(f'found {numdiscard} sequences with incorrect accession format')
    numseq = len(newfile)
    os.remove('CRABS_bold_download.fasta')

    return numseq
